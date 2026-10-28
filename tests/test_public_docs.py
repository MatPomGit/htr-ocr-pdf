"""Keep the public MkDocs site limited to technical documentation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicDocumentationTest(unittest.TestCase):
    def test_public_pages_contain_no_user_groups_or_use_case_descriptions(self):
        pages = sorted((ROOT / "docs").glob("**/*.md"))
        self.assertGreaterEqual(len(pages), 8)
        # No descriptions of audiences, grading, research pilots or usage scenarios.
        forbidden = [
            r"student", r"ocenian", r"pilotaż", r"badawcz",
            r"przeznaczen", r"eksperyment", r"scenariusz zastosowan",
        ]
        for page in [ROOT / "README.md", *pages]:
            data = page.read_text(encoding="utf-8").casefold()
            for term in forbidden:
                with self.subTest(file=page.name, term=term):
                    self.assertIsNone(re.search(term, data), f"{page}: {term}")

    def test_mkdocs_configuration_and_pages_exist(self):
        config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        self.assertIn("name: material", config)
        self.assertIn("docs_dir: docs", config)
        for file in ("index.md", "installation.md", "interface.md", "compression.md",
                     "recognition.md", "results.md", "evaluation.md", "architecture.md",
                     "development.md", "troubleshooting.md"):
            self.assertTrue((ROOT / "docs" / file).is_file(), file)

    def test_instructions_document_immediate_cancellation(self):
        text = (ROOT / "docs" / "recognition.md").read_text(encoding="utf-8")
        self.assertIn("stream: true", text)
        self.assertIn("CancelToken", text)
        self.assertIn("gniazdo TCP", text)


if __name__ == "__main__":
    unittest.main()
