"""Lossless/lossy PDF compression and searchable HTR overlays (local processing)."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import os


@dataclass(frozen=True)
class CompressionPreset:
    quality: int | None
    scale: float


PRESETS = {
    "lossless": CompressionPreset(None, 1.0),
    "light": CompressionPreset(88, 1.0),
    "medium": CompressionPreset(72, 0.85),
    "strong": CompressionPreset(50, 0.70),
}


def _validate_paths(source: Path, target: Path) -> None:
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("Plik źródłowy musi być istniejącym PDF-em.")
    if source.resolve() == target.resolve():
        raise ValueError("Nie wolno nadpisywać oryginalnego pliku PDF.")
    if target.suffix.lower() != ".pdf":
        raise ValueError("Plik wynikowy musi mieć rozszerzenie .pdf.")


def compress_pdf(source: Path, target: Path, profile: str, progress=None) -> dict:
    """Preserve vector content; only eligible image XObjects are JPEG-reencoded.

    Unsupported/masked images are left untouched; never blindly rasterize pages.
    'lossless' rewrites the document without replacing any image pixels.
    """
    import pymupdf
    from PIL import Image

    if profile not in PRESETS:
        raise ValueError(f"Nieznany profil kompresji: {profile}")
    source, target = Path(source), Path(target)
    _validate_paths(source, target)
    preset = PRESETS[profile]
    replaced = 0
    skipped = 0
    with pymupdf.open(source) as doc:
        if doc.needs_pass:
            raise ValueError("Zaszyfrowane PDF-y nie są obsługiwane.")
        pages = len(doc)
        if pages < 1:
            raise ValueError("Dokument PDF nie zawiera stron.")
        if preset.quality is not None:
            candidates = {}
            for page in doc:
                for info in page.get_images(full=True):
                    xref, smask = info[0], info[1]
                    if xref not in candidates:
                        candidates[xref] = smask
                    else:
                        candidates[xref] = max(candidates[xref], smask)
            for xref, smask in candidates.items():
                try:
                    # Transparency and unusual image constructions are not safe
                    # to replace with opaque 8-bit JPEG streams.
                    if smask or doc.xref_get_key(xref, "ImageMask")[1] == "true":
                        skipped += 1
                        continue
                    obj = doc.extract_image(xref)
                    with Image.open(BytesIO(obj["image"])) as im:
                        if im.mode in {"RGBA", "LA", "P"} and "transparency" in im.info:
                            skipped += 1
                            continue
                        if im.mode not in {"RGB", "L"}:
                            im = im.convert("RGB")
                        im.load()
                        if im.width < 40 or im.height < 40:
                            skipped += 1
                            continue
                        if preset.scale != 1.0:
                            dims = (max(1, round(im.width * preset.scale)),
                                    max(1, round(im.height * preset.scale)))
                            im = im.resize(dims, Image.Resampling.LANCZOS)
                        encoded = BytesIO()
                        im.save(encoded, format="JPEG", quality=preset.quality,
                                optimize=True, subsampling=0)
                        data = encoded.getvalue()
                        if len(data) >= len(obj["image"]):
                            skipped += 1
                            continue
                        doc.update_stream(xref, data, compress=False)
                        doc.xref_set_key(xref, "Filter", "/DCTDecode")
                        doc.xref_set_key(xref, "DecodeParms", "null")
                        doc.xref_set_key(xref, "ColorSpace", "/DeviceGray" if im.mode == "L" else "/DeviceRGB")
                        doc.xref_set_key(xref, "BitsPerComponent", "8")
                        doc.xref_set_key(xref, "Width", str(im.width))
                        doc.xref_set_key(xref, "Height", str(im.height))
                        # ICCBased /Decode arrays no longer apply after RGB encoding.
                        doc.xref_set_key(xref, "Decode", "null")
                        replaced += 1
                    if progress:
                        progress(f"Zakodowano obraz {xref} jako JPEG (profil {profile}).")
                except (OSError, ValueError, RuntimeError):
                    # Unknown/unsupported images are preserved, never removed.
                    skipped += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".partial.pdf")
        try:
            doc.save(tmp, garbage=4, deflate=True, deflate_images=True,
                     deflate_fonts=True, use_objstms=1)
            with pymupdf.open(tmp) as verify:
                if len(verify) != pages:
                    raise RuntimeError("Niezgodna liczba stron po kompresji.")
                for i in range(pages):
                    if abs(verify[i].rect.width - doc[i].rect.width) > 0.1 or abs(verify[i].rect.height - doc[i].rect.height) > 0.1:
                        raise RuntimeError(f"Zmieniono wymiary strony {i+1}.")
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    return {"profile": profile, "pages": pages, "images_reencoded": replaced,
            "images_skipped": skipped, "source_bytes": source.stat().st_size,
            "output_bytes": target.stat().st_size}


def _font_path() -> str | None:
    """Find a Unicode-capable font available with the host operating system."""
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates = (
        Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path.home() / "Library" / "Fonts" / "DejaVuSans.ttf",
        windows_fonts / "arial.ttf",
        windows_fonts / "segoeui.ttf",
    )
    return next((str(path) for path in candidates if path.is_file()), None)


def export_searchable_pdf(source: Path, target: Path, pages: list[dict],
                          text_key: str, font_path: str | None = None) -> dict:
    """Keep the source pages and add *invisible, approximate* searchable text.

    HTR supplies text per horizontal segment, not word bounding boxes.
    Search and text extraction work; precise selection boxes are NOT claimed.
    """
    import pymupdf

    source, target = Path(source), Path(target)
    _validate_paths(source, target)
    font_path = font_path or _font_path()
    if font_path is None:
        raise RuntimeError("Brak czcionki Unicode. Zainstaluj DejaVu Sans lub podaj font_path.")
    with pymupdf.open(source) as doc:
        if doc.needs_pass:
            raise ValueError("Zaszyfrowane PDF-y nie są obsługiwane.")
        count = 0
        page_count = len(doc)
        for item in pages:
            page_no = int(item["page"])
            if not 1 <= page_no <= len(doc):
                raise ValueError(f"Nieprawidłowy numer strony: {page_no}")
            content = item.get(text_key, "").strip()
            if not content:
                continue
            page = doc[page_no - 1]
            # Use Unicode font; hidden text does not alter scanned page appearance.
            name = "HTRUnicode"
            page.insert_font(fontname=name, fontfile=font_path)
            font = pymupdf.Font(fontfile=font_path)
            cuts = item.get("segment_row_boundaries", [])
            image_size = item.get("image_size", [])
            segments = item.get(text_key.replace("_text", "_segments"), [])
            if not (segments and len(cuts) == len(segments) + 1 and len(image_size) == 2 and image_size[1]):
                cuts, segments = [0, 1], [content]
                pixel_height = 1
            else:
                pixel_height = image_size[1]
            left = max(2.0, page.rect.width * 0.025)
            usable = page.rect.width - left * 2
            for j, segment in enumerate(segments):
                lines = [line.strip() for line in segment.splitlines() if line.strip()]
                if not lines:
                    continue
                y0 = page.rect.height * cuts[j] / pixel_height
                y1 = page.rect.height * cuts[j + 1] / pixel_height
                for idx, line in enumerate(lines):
                    y = min(page.rect.height - 2, max(8, y0 + (y1 - y0) * (idx + .5) / len(lines)))
                    font_size = min(10.0, max(2.0, usable / max(font.text_length(line, fontsize=1), .001)))
                    # Invisible PDF text rendering mode 3; remains selectable/searchable.
                    page.insert_text((left, y), line, fontname=name, fontsize=font_size,
                                     render_mode=3, overlay=True)
                    count += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".partial.pdf")
        try:
            doc.save(tmp, garbage=4, deflate=True, use_objstms=1)
            with pymupdf.open(tmp) as verify:
                if len(verify) != len(doc):
                    raise RuntimeError("Błąd eksportu PDF: liczba stron uległa zmianie.")
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    return {"pages": page_count, "invisible_text_lines": count, "path": str(target)}
