import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdf_tools import compress_pdf, export_searchable_pdf, PRESETS


class PdfToolsTest(unittest.TestCase):
    def make_pdf(self, destination):
        import pymupdf
        from PIL import Image, ImageDraw
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=400)
        page.insert_text((30, 55), 'Printed text 123')
        page.draw_line((10, 90), (290, 90), color=(0, 0, 1), width=2)
        im = Image.effect_noise((900, 600), 55).convert('RGB')
        d = ImageDraw.Draw(im)
        for y in range(0, 600, 17):
            d.text((30, y), f'odręczne pytanie {y}', fill=(20, 20, 20))
        buf = io.BytesIO()
        im.save(buf, format='PNG')
        page.insert_image(pymupdf.Rect(20, 120, 280, 360), stream=buf.getvalue())
        doc.set_metadata({'title': 'Test PDF'})
        doc.save(destination)
        doc.close()

    def test_presets_and_lossless(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            src = p / 'original.pdf'
            self.make_pdf(src)
            self.assertEqual(set(PRESETS), {'lossless', 'light', 'medium', 'strong'})
            out = p / 'lossless.pdf'
            result = compress_pdf(src, out, 'lossless')
            self.assertEqual(result['images_reencoded'], 0)
            with pymupdf.open(src) as before, pymupdf.open(out) as after:
                self.assertEqual(before[0].get_text(), after[0].get_text())
                self.assertEqual(before[0].get_pixmap().samples, after[0].get_pixmap().samples)
                self.assertEqual(after.metadata['title'], 'Test PDF')

    def test_lossy_preserves_vector_text_and_image_geometry(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            src = p / 'input.pdf'
            self.make_pdf(src)
            for profile in ('light', 'medium', 'strong'):
                target = p / f'{profile}.pdf'
                stats = compress_pdf(src, target, profile)
                self.assertEqual(stats['pages'], 1)
                self.assertEqual(stats['images_reencoded'], 1)
                with pymupdf.open(target) as doc:
                    self.assertIn('Printed text 123', doc[0].get_text())
                    self.assertEqual(len(doc[0].get_images()), 1)
                    self.assertEqual((doc[0].rect.width, doc[0].rect.height), (300, 400))
                    self.assertTrue(doc[0].get_pixmap().samples)

    def test_searchable_pdf_preserves_appearance(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            src, dst = p / 'input.pdf', p / 'output.pdf'
            self.make_pdf(src)
            item = {'page': 1, 'original_text': 'Żółw i zażółć\nCześć świecie',
                    'original_segments': ['Żółw i zażółć', 'Cześć świecie'],
                    'segment_row_boundaries': [0, 500, 1000], 'image_size': [700, 1000]}
            summary = export_searchable_pdf(src, dst, [item], 'original_text')
            self.assertEqual(summary['invisible_text_lines'], 2)
            with pymupdf.open(src) as a, pymupdf.open(dst) as b:
                self.assertEqual(a[0].get_pixmap().samples, b[0].get_pixmap().samples)
                extracted = b[0].get_text()
                self.assertIn('Żółw', extracted)
                self.assertIn('Cześć', extracted)

    def test_source_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'x.pdf'
            self.make_pdf(src)
            with self.assertRaises(ValueError):
                compress_pdf(src, src, 'strong')
            with self.assertRaises(ValueError):
                export_searchable_pdf(src, src, [], 'original_text')


if __name__ == '__main__':
    unittest.main()
