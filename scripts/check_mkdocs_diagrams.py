"""Assert MkDocs generated a diagram container, not a literal code listing."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys


class MermaidContainerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.mermaid_containers = 0
        self.plain_code_mermaid = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        classes = (data.get("class") or "").split()
        if "mermaid" in classes and tag in {"pre", "div"}:
            self.mermaid_containers += 1
        if tag == "code" and any(item.startswith("language-mermaid") for item in classes):
            self.plain_code_mermaid += 1


def check(path: Path) -> None:
    if not path.is_file():
        raise AssertionError(f"Missing generated HTML: {path}")
    html = path.read_text(encoding="utf-8")
    parser = MermaidContainerParser()
    parser.feed(html)
    if parser.mermaid_containers != 1:
        raise AssertionError(
            f"Expected exactly 1 Mermaid container, got {parser.mermaid_containers}. "
            "Check pymdownx.superfences.custom_fences in mkdocs.yml."
        )
    if parser.plain_code_mermaid:
        raise AssertionError("Found unrendered language-mermaid code block.")
    if "Porównanie transkrypcji i obrazu" not in html:
        raise AssertionError("The processing diagram content is missing.")


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("html", type=Path, help="Generated MkDocs page")
    args = cli.parse_args()
    try:
        check(args.html)
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: Mermaid diagram configured in {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
