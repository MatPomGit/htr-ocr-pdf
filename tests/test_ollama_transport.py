"""Wire-level cancellation tests using a local HTTP server (no Ollama needed)."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ollama_transport import CancelToken, Cancelled, stream_chat


class FakeOllamaHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _send_chunk(self, data):
        part = json.dumps(data, ensure_ascii=False).encode("utf-8") + b"\n"
        self.wfile.write(f"{len(part):X}\r\n".encode() + part + b"\r\n")
        self.wfile.flush()

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        size = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(size))
        self.server.requests.append(payload)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            self._send_chunk({"message": {"content": '{"text": '}, "done": False})
            self.server.first_chunk.set()
            if self.server.block:
                # A real server produces tokens slowly; the client must cancel
                # without waiting for this simulated, very slow inference.
                self.server.release.wait(5)
            self._send_chunk({"message": {"content": '"zażółć"}'}, "done": False})
            self._send_chunk({"message": {"content": ""}, "done": True, "done_reason": "stop"})
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.server.client_disconnected.set()


class TransportTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
        self.server.requests = []
        self.server.block = False
        self.server.first_chunk = threading.Event()
        self.server.release = threading.Event()
        self.server.client_disconnected = threading.Event()
        self.loop = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.loop.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.payload = {"model": "mock-local-model",
                        "messages": [{"role": "user", "content": "Test"}],
                        "format": {"type": "object"},
                        "stream": False}

    def tearDown(self):
        self.server.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.loop.join(timeout=2)

    def test_stream_aggregates_fragments(self):
        response = stream_chat(self.base_url, self.payload)
        self.assertEqual(response["message"]["content"], '{"text": "zażółć"}')
        self.assertEqual(response["done_reason"], "stop")
        self.assertTrue(self.server.requests[0]["stream"])

    def test_stop_interrupts_blocked_generation(self):
        self.server.block = True
        stop = CancelToken()
        outcome = []
        worker = threading.Thread(target=lambda: self._collect(outcome, stop), daemon=True)
        worker.start()
        self.assertTrue(self.server.first_chunk.wait(timeout=3))
        started = time.monotonic()
        stop.set()
        worker.join(timeout=1.5)
        self.assertFalse(worker.is_alive(), "Anulowanie nie może czekać na kolejny token Ollama.")
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(outcome, ["cancelled"])
        self.server.release.set()

    def _collect(self, outcome, stop):
        try:
            stream_chat(self.base_url, self.payload, stop=stop)
            outcome.append("completed")
        except Cancelled:
            outcome.append("cancelled")
        except Exception as exc:
            outcome.append(f"error: {exc}")

    def test_cancel_before_connection_prevents_request(self):
        stop = CancelToken()
        stop.set()
        with self.assertRaises(Cancelled):
            stream_chat(self.base_url, self.payload, stop=stop)
        self.assertEqual(self.server.requests, [])

    def test_reset_only_after_request_finishes(self):
        stop = CancelToken()
        reply = stream_chat(self.base_url, self.payload, stop=stop)
        self.assertEqual(reply["done_reason"], "stop")
        stop.set()
        stop.clear()
        self.assertFalse(stop.is_set())


if __name__ == "__main__":
    unittest.main()
