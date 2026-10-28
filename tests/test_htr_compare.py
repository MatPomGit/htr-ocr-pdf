import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from htr_compare import (Config, boundaries, distance, normalize, page_numbers, pair_metrics,
                         reference_metrics, parse_reference, require_local, compare_documents,
                         recognize)


class AlgorithmsTest(unittest.TestCase):
    def test_distance(self):
        self.assertEqual(distance("kitten", "sitting"), 3)
        self.assertEqual(distance([], []), 0)
        self.assertEqual(distance("", "abc"), 3)
        self.assertEqual(distance(["abc", "ghi"], ["abc", "def"]), 1)

    def test_disagreement_not_accuracy(self):
        m = pair_metrics("  Witaj  świecie\n", "Witaj świecie")
        self.assertEqual(m["char_disagreement"], 0)
        self.assertEqual(m["word_disagreement"], 0)
        self.assertAlmostEqual(pair_metrics("kot", "kod")["char_disagreement"], 1 / 3)
        self.assertEqual(reference_metrics("abc", "ab")["cer"], 1 / 3)
        self.assertIsNone(reference_metrics("", "abc")["cer"])
        self.assertEqual(normalize("ż"), "ż")

    def test_pages(self):
        self.assertEqual(page_numbers("1,3-5", 6), [1, 3, 4, 5])
        with self.assertRaises(ValueError):
            page_numbers("5-3", 7)
        with self.assertRaises(ValueError):
            page_numbers("1,10", 7)

    def test_local_guard(self):
        for address in ("https://127.0.0.1:11434", "http://api.example.com:11434",
                        "http://127.0.0.1:11434/evil", "http://127.0.0.1:11434@evil.com"):
            with self.assertRaises(ValueError):
                require_local(address)
        self.assertEqual(require_local("http://127.0.0.1:11434"), "http://127.0.0.1:11434")

    def test_reference(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ref.txt"
            p.write_text("=== PAGE 1 ===\nkot\n=== PAGE 2 ===\npies\n", encoding="utf-8")
            self.assertEqual(parse_reference(p, 2), {1: "kot", 2: "pies"})
            p.write_text("text only", encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_reference(p, 2)

    def test_boundaries(self):
        from PIL import Image
        a = Image.new("RGB", (100, 400), "white")
        cuts = boundaries(a, 3)
        self.assertEqual(cuts[0], 0)
        self.assertEqual(cuts[-1], 400)
        self.assertEqual(len(cuts), 4)
        self.assertTrue(cuts[0] < cuts[1] < cuts[2] < cuts[3])

    def test_recognize_payload(self):
        from PIL import Image
        conf = Config(Path('a.pdf'), Path('b.pdf'), Path('out'))
        with patch('htr_compare.stream_chat', return_value={'message': {'content': '{"text": "rękopis"}'}, 'done_reason': 'stop'}) as mock:
            self.assertEqual(recognize(Image.new('RGB',(100,200),'white'),conf),'rękopis')
            self.assertEqual(mock.call_args.args[1]['messages'][0]['role'], 'user')
            self.assertTrue(mock.call_args.args[1]['messages'][0]['images'][0])
            self.assertEqual(mock.call_args.args[1]['options']['temperature'],0)
            self.assertTrue(mock.call_args.args[1]['stream'])


class IntegratedTest(unittest.TestCase):
    def test_report_with_mock_recognizer(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pdf_a, pdf_b = d / 'original.pdf', d / 'compressed.pdf'
            for path, label in [(pdf_a,'abc'),(pdf_b,'abd')]:
                doc = pymupdf.open()
                page = doc.new_page(width=595, height=842)
                page.insert_text((20, 50), f'Pytanie 1 / {label}')
                doc.save(path)
                doc.close()
            ref = d / 'reference.txt'
            ref.write_text('abc',encoding='utf-8')
            conf = Config(pdf_a,pdf_b,d / 'output',segments=1,max_side=1200,reference=ref)
            with patch('htr_compare.check_model'), patch('htr_compare.recognize',side_effect=['abc','abd']):
                result = compare_documents(conf)
            self.assertEqual(result['summary']['pages_processed'],1)
            self.assertAlmostEqual(result['summary']['char_disagreement'],1/3)
            self.assertEqual(result['summary']['original_cer'],0)
            self.assertAlmostEqual(result['summary']['compressed_cer'],1/3)
            for name in ('report.html','results.json','metrics.csv','original_htr.txt','compressed_htr.txt'):
                self.assertTrue((d/'output'/name).is_file(),name)
            self.assertIn('Oryginał',(d/'output'/'report.html').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((d/'output'/'results.json').read_text(encoding='utf-8'))['model'],'qwen3-vl:4b')

    def test_mismatched_pages_rejected(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            files = [d/'a.pdf',d/'b.pdf']
            for path, count in zip(files,[1,2]):
                doc=pymupdf.open()
                for _ in range(count): doc.new_page()
                doc.save(path)
            with patch('htr_compare.check_model'):
                with self.assertRaisesRegex(ValueError,'Różna liczba stron'):
                    compare_documents(Config(files[0], files[1], d/'out'))


if __name__=='__main__':
    unittest.main()

class LocalApiTest(unittest.TestCase):
    def test_ollama_rest_wire_protocol(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from PIL import Image
        from htr_compare import check_model, recognize

        recorded = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.assert_path('/api/tags')
                self.answer({'models': [{'name':'qwen3-vl:4b','digest':'sha256-test'}]})
            def do_POST(self):
                self.assert_path('/api/chat')
                size=int(self.headers['Content-Length'])
                payload=json.loads(self.rfile.read(size))
                recorded.append(payload)
                self.answer({'message':{'content':'{"text":"odręcznie"}'}, 'done_reason':'stop'})
            def answer(self, data):
                body=json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def assert_path(self,path):
                if self.path != path: raise AssertionError(self.path)
            def log_message(self,*_args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0), Handler)
        thr=threading.Thread(target=server.serve_forever,daemon=True)
        thr.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(check_model(url,'qwen3-vl:4b'),'sha256-test')
            cfg=Config(Path('a.pdf'),Path('b.pdf'),Path('out'),server=url)
            self.assertEqual(recognize(Image.new('RGB',(400,200),'white'),cfg),'odręcznie')
            self.assertEqual(recorded[0]['format']['properties']['text']['type'],'string')
            import base64
            self.assertTrue(base64.b64decode(recorded[0]['messages'][0]['images'][0]).startswith(b'\x89PNG'))
        finally:
            server.shutdown()
            server.server_close()

class ResumeTest(unittest.TestCase):
    def test_checkpoint_resume(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            a, b = d / 'a.pdf', d / 'b.pdf'
            for file in [a, b]:
                doc = pymupdf.open()
                doc.new_page(width=210,height=280)
                doc.new_page(width=210,height=280)
                doc.save(file)
                doc.close()
            cfg = Config(a,b,d/'out',max_side=1200,segments=1)
            with patch('htr_compare.check_model',return_value='digest-test'), patch(
                    'htr_compare.recognize',side_effect=['kot','kot','pies',RuntimeError('simulated interrupted run')]):
                with self.assertRaisesRegex(RuntimeError,'simulated interrupted'):
                    compare_documents(cfg)
            cp = d/'out'/'checkpoint.json'
            self.assertTrue(cp.exists())
            saved=json.loads(cp.read_text(encoding='utf-8'))
            self.assertEqual([p['page'] for p in saved['pages']],[1])
            with patch('htr_compare.check_model',return_value='digest-test'), patch(
                    'htr_compare.recognize',side_effect=['pies','pies']) as mocked:
                result=compare_documents(cfg)
                self.assertEqual(mocked.call_count,2)
            self.assertEqual(result['summary']['pages_processed'],2)
            self.assertFalse(cp.exists())
