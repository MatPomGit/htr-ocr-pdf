"""Cancelable streaming transport for the local Ollama HTTP API.

Closing the active TCP socket is essential: simply setting a flag while an
unstreamed model response is pending does not stop an inference request.
"""
from __future__ import annotations

import http.client
import json
import socket
import threading
from urllib.parse import urlparse


class Cancelled(Exception):
    """User requested cancellation; no partial model output is accepted."""


class CancelToken:
    """Thread-safe cancellation event that can abort the active HTTP socket."""

    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None

    def is_set(self) -> bool:
        return self._event.is_set()

    def clear(self) -> None:
        with self._lock:
            if self._socket is not None:
                raise RuntimeError("Cannot reset cancellation during an active request.")
            self._event.clear()

    def register(self, active_socket: socket.socket) -> None:
        with self._lock:
            if self._event.is_set():
                _abort_socket(active_socket)
                raise Cancelled("Analizę anulowano.")
            self._socket = active_socket

    def unregister(self, active_socket: socket.socket) -> None:
        with self._lock:
            if self._socket is active_socket:
                self._socket = None

    def set(self) -> None:
        with self._lock:
            self._event.set()
            active_socket = self._socket
            self._socket = None
        if active_socket is not None:
            _abort_socket(active_socket)


def _abort_socket(active_socket: socket.socket) -> None:
    try:
        active_socket.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        active_socket.close()
    except OSError:
        pass


def stream_chat(server: str, payload: dict, stop: CancelToken | None = None,
                timeout: int = 900) -> dict:
    """Read Ollama /api/chat streaming JSON lines and combine content.

    The server observes client disconnection when cancellation closes the
    socket. No Ollama process or unrelated concurrent request is killed.
    """
    parsed = urlparse(server)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Ollama musi działać lokalnie.")
    if parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Nieprawidłowy lokalny adres Ollama.")
    if stop is not None and stop.is_set():
        raise Cancelled("Analizę anulowano.")

    conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 11434, timeout=timeout)
    active_socket = None
    response = None
    try:
        conn.connect()
        active_socket = conn.sock
        if active_socket is None:
            raise RuntimeError("Nie udało się otworzyć połączenia z Ollama.")
        if stop is not None:
            stop.register(active_socket)
        body = json.dumps({**payload, "stream": True}, ensure_ascii=False).encode("utf-8")
        conn.request(
            "POST", "/api/chat", body=body,
            headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
        )
        response = conn.getresponse()
        if response.status != 200:
            error = response.read(2048).decode("utf-8", "replace")
            raise RuntimeError(f"Ollama HTTP {response.status}: {error}")

        fragments: list[str] = []
        result: dict = {}
        complete = False
        while True:
            if stop is not None and stop.is_set():
                raise Cancelled("Analizę anulowano.")
            line = response.readline()
            if not line:
                break
            if not line.strip():
                continue
            try:
                part = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Ollama zwróciła uszkodzony strumień JSON.") from exc
            if "error" in part:
                raise RuntimeError(f"Błąd Ollama: {part['error']}")
            fragments.append(part.get("message", {}).get("content", ""))
            result = part
            if part.get("done") is True or ("done_reason" in part and "done" not in part):
                complete = True
                break
        if stop is not None and stop.is_set():
            raise Cancelled("Analizę anulowano.")
        if not complete:
            raise RuntimeError("Strumień Ollama został przerwany przed zakończeniem odpowiedzi.")
        return {"message": {"content": "".join(fragments)},
                "done_reason": result.get("done_reason")}
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        if stop is not None and stop.is_set():
            raise Cancelled("Analizę anulowano.") from exc
        raise RuntimeError(f"Błąd lokalnego połączenia z Ollama: {exc}") from exc
    finally:
        if stop is not None and active_socket is not None:
            stop.unregister(active_socket)
        if response is not None:
            try:
                response.close()
            except OSError:
                pass
        conn.close()
