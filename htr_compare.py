#!/usr/bin/env python3
"""HTR PDF Compare 1.2.1: local, privacy-preserving paired PDF transcription."""
from __future__ import annotations

import argparse
import base64
import csv
from dataclasses import dataclass
import datetime as dt
from difflib import HtmlDiff
import hashlib
from html import escape
from io import BytesIO
import json
import math
from pathlib import Path
import queue
import re
import threading
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ollama_transport import CancelToken, Cancelled, stream_chat

APP_VERSION = "1.2.1"
DEFAULT_MODEL = "qwen3-vl:4b"
DEFAULT_SERVER = "http://127.0.0.1:11434"
SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}

PROMPTS = {
    "handwriting": (
        "Przepisz DOSŁOWNIE wyłącznie pismo odręczne widoczne na obrazie. "
        "Ignoruj wydrukowane pytania, numery pozycji, nagłówki, linie formularza i ramki. "
        "Zachowaj polskie znaki, kolejność od góry do dołu oraz podział na wiersze. "
        "Nie poprawiaj języka ani błędów, nie zgaduj na podstawie treści pytania. "
        "Jeśli fragment jest nieczytelny, wpisz [nieczytelne]; jeśli nie ma pisma odręcznego, zwróć pusty tekst. "
        "Zwróć wyłącznie obiekt JSON z polem text."
    ),
    "all": (
        "Przepisz DOSŁOWNIE wszystkie widoczne napisy, drukowane i odręczne, "
        "w kolejności czytania od góry do dołu. Zachowaj polskie znaki i podział wierszy. "
        "Nie poprawiaj ani nie uzupełniaj treści. Nieczytelne fragmenty oznacz [nieczytelne]. "
        "Zwróć wyłącznie obiekt JSON z polem text."
    ),
}


@dataclass
class Config:
    original: Path
    compressed: Path
    output: Path
    model: str = DEFAULT_MODEL
    server: str = DEFAULT_SERVER
    mode: str = "handwriting"
    segments: int = 2
    max_side: int = 2800
    pages: str = ""
    reference: Path | None = None
    searchable_pdf: bool = True


def require_local(server: str) -> str:
    parsed = urlparse(server)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise ValueError("Ollama musi działać lokalnie (http://127.0.0.1:11434). Serwery zdalne są zablokowane.")
    return server.rstrip("/")


def http_json(url: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"},
                      method="POST" if payload is not None else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        body = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {body}") from exc
    except (URLError, TimeoutError, ConnectionError) as exc:
        raise RuntimeError(f"Brak połączenia z lokalnym Ollama: {exc}") from exc


def check_model(server: str, model: str) -> str | None:
    available = http_json(server + "/api/tags", timeout=20)
    names = {x.get("name", "") for x in available.get("models", [])}
    if model not in names and not (":" not in model and model + ":latest" in names):
        raise RuntimeError(f"Model '{model}' nie jest pobrany. Uruchom: ollama pull {model}")
    target = model if ":" in model else model + ":latest"
    return next((x.get("digest") for x in available.get("models", []) if x.get("name") == target), None)


def recognize(image, config: Config, stop: CancelToken | threading.Event | None = None) -> str:
    if stop is not None and stop.is_set():
        raise Cancelled("Analizę anulowano.")
    data = BytesIO()
    image.save(data, format="PNG", optimize=False)
    payload = {
        "model": config.model,
        "messages": [{
            "role": "user",
            "content": PROMPTS[config.mode],
            "images": [base64.b64encode(data.getvalue()).decode("ascii")],
        }],
        "format": SCHEMA,
        "options": {"temperature": 0, "seed": 42, "num_predict": 3000, "num_ctx": 8192},
        "stream": True,
        "keep_alive": "5m",
    }
    reply = stream_chat(config.server, payload, stop=stop, timeout=900)
    if reply.get("done_reason") == "length":
        raise RuntimeError("Model przerwał transkrypcję z powodu limitu tokenów; zwiększ liczbę pasów strony.")
    content = reply.get("message", {}).get("content", "")
    try:
        obj = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Model nie zwrócił poprawnego JSON: {str(content)[:250]}") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("text"), str):
        raise RuntimeError("Niepoprawny schemat odpowiedzi HTR. Brak pola 'text'.")
    return obj["text"].strip()


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def distance(seq_a, seq_b) -> int:
    """Exact Levenshtein with O(min(n, m)) memory, works for strings/tokens."""
    if len(seq_a) < len(seq_b):
        seq_a, seq_b = seq_b, seq_a
    old = list(range(len(seq_b) + 1))
    for i, a in enumerate(seq_a, 1):
        cur = [i]
        for j, b in enumerate(seq_b, 1):
            cur.append(min(cur[j - 1] + 1, old[j] + 1, old[j - 1] + (a != b)))
        old = cur
    return old[-1]


def pair_metrics(a: str, b: str) -> dict:
    a, b = normalize(a), normalize(b)
    aw, bw = a.split(), b.split()
    dc, dw = distance(a, b), distance(aw, bw)
    # Symmetric 'disagreement' denominator; not an accuracy metric.
    clen, wlen = max(len(a), len(b)), max(len(aw), len(bw))
    return {"char_edits": dc, "word_edits": dw,
            "char_denominator": clen, "word_denominator": wlen,
            "char_disagreement": dc / clen if clen else 0.0,
            "word_disagreement": dw / wlen if wlen else 0.0}


def reference_metrics(reference: str, prediction: str) -> dict:
    r, p = normalize(reference), normalize(prediction)
    rw = r.split()
    return {
        "cer": distance(r, p) / len(r) if r else (0.0 if not p else None),
        "wer": distance(rw, p.split()) / len(rw) if rw else (0.0 if not p else None),
        "reference_characters": len(r), "reference_words": len(rw),
    }


def parse_reference(path: Path, page_count: int) -> dict[int, str]:
    text = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r"(?im)^===\s*(?:PAGE|STRONA)\s+(\d+)\s*===\s*$")
    markers = list(pattern.finditer(text))
    if not markers:
        if page_count != 1:
            raise ValueError("Dla wielu stron referencja TXT musi zawierać znaczniki '=== PAGE 1 ===', itd.")
        return {1: text.strip()}
    result = {}
    for i, match in enumerate(markers):
        page = int(match.group(1))
        if page < 1 or page > page_count or page in result:
            raise ValueError(f"Nieprawidłowy lub powtórzony numer strony w referencji: {page}")
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        result[page] = text[match.end():end].strip()
    return result


def page_numbers(spec: str, count: int) -> list[int]:
    if not spec.strip():
        return list(range(1, count + 1))
    numbers: set[int] = set()
    for chunk in spec.replace(" ", "").split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", chunk)
        if not m:
            raise ValueError(f"Niepoprawny zakres stron: {chunk}")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if not 1 <= a <= b <= count:
            raise ValueError(f"Strony poza dokumentem: {chunk}; zakres 1-{count}")
        numbers.update(range(a, b + 1))
    return sorted(numbers)


def boundaries(image, n: int) -> list[int]:
    """Choose white-ish rows near equal thirds; reuse exact cuts for both PDFs."""
    w, h = image.size
    if n == 1:
        return [0, h]
    # 320-pixel thumbnail keeps row positions; avoids heavy full-image scans.
    gray = image.convert("L").resize((min(320, w), h))
    thumb_w = gray.width
    pixels = gray.tobytes()
    ink = [sum(1 for px in pixels[y * thumb_w:(y + 1) * thumb_w] if px < 190)
           for y in range(h)]
    cuts = [0]
    for j in range(1, n):
        target = round(h * j / n)
        span = max(10, h // (n * 9))
        lo = max(cuts[-1] + 25, target - span)
        hi = min(h - 25 * (n - j), target + span)
        cut = min(range(lo, hi + 1), key=lambda row: (ink[row], abs(row - target))) if lo <= hi else target
        cuts.append(cut)
    cuts.append(h)
    return cuts


def image_metrics(a, b) -> dict:
    from PIL import ImageChops, ImageStat
    if a.size != b.size:
        raise ValueError("Strony różnią się rozmiarami obrazu po renderowaniu.")
    delta = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    root_mean_square = math.sqrt(sum(v * v for v in ImageStat.Stat(delta).rms) / 3)
    return {"rmse_normalized": root_mean_square / 255.0,
            "psnr_db": round(20 * math.log10(255.0 / root_mean_square), 4) if root_mean_square else None,
            "identical_pixels": root_mean_square == 0.0}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def render_page(page, dpi: float):
    from PIL import Image
    import pymupdf
    pixmap = page.get_pixmap(dpi=round(dpi), colorspace=pymupdf.csRGB, alpha=False)
    # No lossy intermediate encoding.
    return Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")


def compare_documents(config: Config, progress=None, stop: threading.Event | None = None) -> dict:
    import pymupdf

    def log(message: str):
        if progress:
            progress(message)

    config.server = require_local(config.server)
    if config.mode not in PROMPTS:
        raise ValueError("Nieprawidłowy tryb transkrypcji.")
    if not 1 <= config.segments <= 6:
        raise ValueError("Liczba pasów musi należeć do zakresu 1–6.")
    if not 1200 <= config.max_side <= 6000:
        raise ValueError("Maksymalny wymiar obrazu musi należeć do zakresu 1200–6000 px.")
    if not config.original.is_file() or not config.compressed.is_file():
        raise FileNotFoundError("Nie odnaleziono jednego z plików PDF.")
    if config.original.resolve() == config.compressed.resolve():
        raise ValueError("Wybierz dwa różne pliki PDF.")
    log("Sprawdzam lokalny silnik Ollama i model…")
    model_digest = check_model(config.server, config.model)
    if stop is not None and stop.is_set():
        raise Cancelled("Analizę anulowano.")
    if not isinstance(model_digest, str):
        model_digest = None
    try:
        first = pymupdf.open(config.original)
        second = pymupdf.open(config.compressed)
    except Exception as exc:
        raise RuntimeError(f"Nie można odczytać PDF: {exc}") from exc
    with first, second:
        if first.needs_pass or second.needs_pass:
            raise ValueError("Zaszyfrowane PDF-y nie są obsługiwane. Najpierw odblokuj je lokalnie.")
        if len(first) != len(second):
            raise ValueError(f"Różna liczba stron ({len(first)} i {len(second)}). Porównanie wymaga par stron 1:1.")
        if len(first) == 0:
            raise ValueError("PDF nie zawiera stron.")
        chosen = page_numbers(config.pages, len(first))
        references = parse_reference(config.reference, len(first)) if config.reference else {}
        hashes = {"original": sha256(config.original), "compressed": sha256(config.compressed)}
        run_key = hashlib.sha256(json.dumps({
            "hashes": hashes, "model": config.model, "model_digest": model_digest,
            "mode": config.mode, "segments": config.segments,
            "max_side": config.max_side, "pages": chosen,
        }, sort_keys=True).encode()).hexdigest()
        config.output.mkdir(parents=True, exist_ok=True)
        checkpoint = config.output / "checkpoint.json"
        previous = {}
        if checkpoint.is_file():
            try:
                state = json.loads(checkpoint.read_text(encoding="utf-8"))
                if state.get("run_key") == run_key:
                    previous = {entry["page"]: entry for entry in state.get("pages", [])}
                    log(f"Wznawiam analizę: zapisano już {len(previous)} stron.")
                else:
                    log("Poprzedni checkpoint dotyczy innych plików lub ustawień; rozpoczynam od początku.")
            except (ValueError, KeyError, TypeError):
                log("Checkpoint jest nieczytelny; rozpoczynam od początku.")
        results = []
        for index, page_no in enumerate(chosen, 1):
            if stop and stop.is_set():
                raise Cancelled("Analizę zatrzymano.")
            if page_no in previous:
                item = previous[page_no]
                # Reference files can be updated without re-running HTR.
                item.pop("reference_text", None)
                item.pop("original_accuracy", None)
                item.pop("compressed_accuracy", None)
                if page_no in references:
                    item["reference_text"] = references[page_no]
                    item["original_accuracy"] = reference_metrics(references[page_no], item["original_text"])
                    item["compressed_accuracy"] = reference_metrics(references[page_no], item["compressed_text"])
                results.append(item)
                log(f"Strona {page_no}/{len(first)}: użyto zapisanej transkrypcji.")
                continue
            p1, p2 = first[page_no - 1], second[page_no - 1]
            if abs(p1.rect.width - p2.rect.width) > 1 or abs(p1.rect.height - p2.rect.height) > 1:
                raise ValueError(f"Strona {page_no}: inne rozmiary stron PDF. Nie mogę porównać tych samych regionów.")
            dpi = min(300.0, 72.0 * config.max_side / max(p1.rect.width, p1.rect.height))
            log(f"Strona {page_no}/{len(first)} ({index}/{len(chosen)}): renderowanie {round(dpi)} DPI…")
            a, b = render_page(p1, dpi), render_page(p2, dpi)
            if stop is not None and stop.is_set():
                raise Cancelled("Analizę anulowano.")
            if a.size != b.size:
                raise ValueError(f"Strona {page_no}: różne rozmiary obrazu po renderowaniu.")
            pixels = image_metrics(a, b)
            cuts = boundaries(a, config.segments)
            chunks_a, chunks_b = [], []
            for segment_no, (upper, lower) in enumerate(zip(cuts[:-1], cuts[1:]), 1):
                if stop and stop.is_set():
                    raise Cancelled("Analizę zatrzymano.")
                region = (0, upper, a.width, lower)
                log(f"Strona {page_no}, pas {segment_no}/{config.segments}: HTR oryginału…")
                chunks_a.append(recognize(a.crop(region), config, stop=stop))
                if stop and stop.is_set():
                    raise Cancelled("Analizę zatrzymano.")
                log(f"Strona {page_no}, pas {segment_no}/{config.segments}: HTR kompresji…")
                chunks_b.append(recognize(b.crop(region), config, stop=stop))
            text_a = "\n".join(t for t in chunks_a if t).strip()
            text_b = "\n".join(t for t in chunks_b if t).strip()
            metrics = pair_metrics(text_a, text_b)
            item = {"page": page_no, "render_dpi": round(dpi), "image_size": list(a.size),
                    "segment_row_boundaries": cuts, "original_text": text_a, "compressed_text": text_b,
                    "original_segments": chunks_a, "compressed_segments": chunks_b,
                    "comparison": metrics, "image_metrics": pixels}
            if page_no in references:
                item["reference_text"] = references[page_no]
                item["original_accuracy"] = reference_metrics(references[page_no], text_a)
                item["compressed_accuracy"] = reference_metrics(references[page_no], text_b)
            results.append(item)
            # Atomic checkpoint: completed pages survive interruptions and Ollama failures.
            tmp = checkpoint.with_suffix(".tmp")
            tmp.write_text(json.dumps({"run_key": run_key, "pages": results},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(checkpoint)
            log(f"Strona {page_no}: rozbieżność znakowa {metrics['char_disagreement']:.1%}.")
        if stop is not None and stop.is_set():
            raise Cancelled("Analizę anulowano.")
        overall_chars = sum(x["comparison"]["char_edits"] for x in results)
        overall_words = sum(x["comparison"]["word_edits"] for x in results)
        denom_c = sum(x["comparison"]["char_denominator"] for x in results)
        denom_w = sum(x["comparison"]["word_denominator"] for x in results)
        summary = {"pages_processed": len(results), "pages_total": len(first),
                   "char_disagreement": overall_chars / denom_c if denom_c else 0.0,
                   "word_disagreement": overall_words / denom_w if denom_w else 0.0}
        if references:
            for label, key in [("original", "original_text"), ("compressed", "compressed_text")]:
                # Aggregate per page; count only valid, nonempty references.
                items = [x for x in results if x.get("reference_text") and normalize(x["reference_text"])]
                reference_chars = sum(len(normalize(x["reference_text"])) for x in items)
                reference_words = sum(len(normalize(x["reference_text"]).split()) for x in items)
                summary[f"{label}_cer"] = (sum(distance(normalize(x["reference_text"]), normalize(x[key]))
                                              for x in items) / reference_chars) if reference_chars else None
                summary[f"{label}_wer"] = (sum(distance(normalize(x["reference_text"]).split(), normalize(x[key]).split())
                                              for x in items) / reference_words) if reference_words else None
            summary["reference_pages"] = sum("reference_text" in x for x in results)
        output = {"application": f"HTR PDF Compare {APP_VERSION}",
                  "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "model": config.model, "model_digest": model_digest if isinstance(model_digest, str) else None,
                  "mode": config.mode,
                  "options": {"temperature": 0, "seed": 42, "segments": config.segments,
                              "max_side": config.max_side, "pages": config.pages or "all"},
                  "files": {
                      "original": {"name": config.original.name, "size": config.original.stat().st_size,
                                   "sha256": hashes["original"]},
                      "compressed": {"name": config.compressed.name, "size": config.compressed.stat().st_size,
                                     "sha256": hashes["compressed"]}},
                  "summary": summary, "pages": results}
        config.output.mkdir(parents=True, exist_ok=True)
        (config.output / "results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        write_outputs(config.output, output)
        if config.searchable_pdf:
            from pdf_tools import export_searchable_pdf
            for label, src, key in (("original", config.original, "original_text"),
                                    ("compressed", config.compressed, "compressed_text")):
                dst = config.output / f"{label}_searchable.pdf"
                log(f"Zapisuję przeszukiwalny PDF: {dst.name}...")
                export_searchable_pdf(src, dst, results, key)
            output["searchable_pdfs"] = ["original_searchable.pdf", "compressed_searchable.pdf"]
            (config.output / "results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        checkpoint.unlink(missing_ok=True)
        log(f"Zakończono. Raport: {config.output / 'report.html'}")
        return output


def format_pct(val) -> str:
    return "brak" if val is None else f"{val:.2%}"


def write_outputs(folder: Path, output: dict) -> None:
    pages = output["pages"]
    (folder / "original_htr.txt").write_text(
        "\n\n".join(f"=== PAGE {x['page']} ===\n{x['original_text']}" for x in pages) + "\n", encoding="utf-8")
    (folder / "compressed_htr.txt").write_text(
        "\n\n".join(f"=== PAGE {x['page']} ===\n{x['compressed_text']}" for x in pages) + "\n", encoding="utf-8")
    with (folder / "metrics.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["page", "char_disagreement", "word_disagreement",
                           "char_edits", "word_edits", "image_rmse", "psnr_db", "original_cer",
                           "compressed_cer", "original_wer", "compressed_wer"])
        writer.writeheader()
        for x in pages:
            row = {"page": x["page"],
                   "char_disagreement": x["comparison"]["char_disagreement"],
                   "word_disagreement": x["comparison"]["word_disagreement"],
                   "char_edits": x["comparison"]["char_edits"],
                   "word_edits": x["comparison"]["word_edits"],
                   "image_rmse": x["image_metrics"]["rmse_normalized"],
                   "psnr_db": x["image_metrics"]["psnr_db"],
                   "original_cer": x.get("original_accuracy", {}).get("cer"),
                   "compressed_cer": x.get("compressed_accuracy", {}).get("cer"),
                   "original_wer": x.get("original_accuracy", {}).get("wer"),
                   "compressed_wer": x.get("compressed_accuracy", {}).get("wer")}
            writer.writerow(row)
    s = output["summary"]
    accuracy = ""
    if "reference_pages" in s:
        accuracy = (f"<p>Transkrypcja wzorcowa ({s['reference_pages']} stron): "
                    f"CER oryginału <b>{format_pct(s.get('original_cer'))}</b>, "
                    f"CER po kompresji <b>{format_pct(s.get('compressed_cer'))}</b>; "
                    f"WER oryginału <b>{format_pct(s.get('original_wer'))}</b>, "
                    f"WER po kompresji <b>{format_pct(s.get('compressed_wer'))}</b>.</p>")
    rows = []
    for x in pages:
        p = x["page"]
        m = x["comparison"]
        diff = HtmlDiff(wrapcolumn=75).make_table(
            x["original_text"].splitlines(), x["compressed_text"].splitlines(),
            fromdesc="Oryginał", todesc="Po kompresji", context=False, numlines=1)
        gt = ""
        if "reference_text" in x:
            gt = (f"<p>Wzorzec: CER {format_pct(x['original_accuracy']['cer'])} → "
                  f"{format_pct(x['compressed_accuracy']['cer'])}; WER "
                  f"{format_pct(x['original_accuracy']['wer'])} → {format_pct(x['compressed_accuracy']['wer'])}.</p>"
                  f"<details><summary>Transkrypcja wzorcowa</summary><pre>{escape(x['reference_text'])}</pre></details>")
        rows.append(f"<section><h2>Strona {p}</h2>"
                    f"<p>Rozbieżność HTR: znaki <b>{format_pct(m['char_disagreement'])}</b>, "
                    f"słowa <b>{format_pct(m['word_disagreement'])}</b>. "
                    f"RMSE obrazu {x['image_metrics']['rmse_normalized']:.5f}, "
                    f"PSNR {x['image_metrics']['psnr_db'] if x['image_metrics']['psnr_db'] is not None else '∞'} dB.</p>"
                    f"{gt}<div class='diff-container'>{diff}</div></section>")
    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raport HTR porównania PDF</title><style>
body{{font:15px/1.55 system-ui,sans-serif;max-width:1180px;margin:0 auto;padding:22px;color:#19232c;background:#fafafa}}
section{{background:white;margin:22px 0;padding:22px;border:1px solid #dde2e5;border-radius:10px}}
small,.note{{color:#52616b}}.diff-container{{overflow-x:auto}}table.diff{{font:12px/1.45 monospace;min-width:650px;border-collapse:collapse;width:100%}}
.diff td,.diff th{{border:1px solid #ddd;padding:4px 7px;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}}
.diff_header{{background:#edf0f3}}.diff_add{{background:#d9f4dc}}.diff_chg{{background:#fff2b6}}.diff_sub{{background:#ffd9d9}}
pre{{white-space:pre-wrap}}h1{{font-size:26px}}h2{{font-size:20px}}
</style></head><body><h1>Porównanie HTR: PDF oryginalny i skompresowany</h1>
<p>Model: <b>{escape(output['model'])}</b>; tryb: <b>{escape(output['mode'])}</b>; "
strony: {s['pages_processed']} / {s['pages_total']}</p>
<p>Rozbieżność znakowa <b>{format_pct(s['char_disagreement'])}</b>; słowna <b>{format_pct(s['word_disagreement'])}</b>.</p>
{accuracy}
<p class="note"><b>Ważne:</b> Bez referencji od człowieka rozbieżność oznacza niezgodność dwóch transkrypcji, NIE rzeczywisty CER/WER ani degradację dokładności. Model HTR może popełnić taki sam błąd w obu wersjach.</p>
{''.join(rows)}</body></html>"""
    (folder / "report.html").write_text(html, encoding="utf-8")


def run_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        raise RuntimeError("Brak Tkinter. Fedora: sudo dnf install python3-tkinter") from exc

    from gui_tooltips import BUTTON_HELP, FIELD_HELP, attach_tooltip

    root = tk.Tk()
    root.title(f"HTR PDF Compare {APP_VERSION} | lokalnie")
    root.geometry("820x720")
    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)
    paths = {name: tk.StringVar() for name in ("original", "compressed", "reference", "output")}
    paths["output"].set(str(Path.home() / "Pobrane" / "htr_comparison"))
    model = tk.StringVar(value=DEFAULT_MODEL)
    mode = tk.StringVar(value="handwriting")
    segments = tk.IntVar(value=2)
    max_side = tk.StringVar(value="2800")
    pages = tk.StringVar(value="")
    compression_profile = tk.StringVar(value="medium")
    searchable_pdf = tk.BooleanVar(value=True)
    events: queue.Queue = queue.Queue()
    stop = CancelToken()
    is_running = False

    def choose(name: str, folder=False):
        if folder:
            value = filedialog.askdirectory(title="Folder raportu")
        elif name == "reference":
            value = filedialog.askopenfilename(filetypes=[("Tekst UTF-8", "*.txt"), ("Wszystkie", "*")])
        else:
            value = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("Wszystkie", "*")])
        if value:
            paths[name].set(value)

    for i, (name, label) in enumerate([
        ("original", "PDF oryginalny"), ("compressed", "PDF skompresowany"),
        ("reference", "Transkrypcja wzorcowa TXT (opcjonalnie)"),
        ("output", "Folder raportu")]):
        caption = ttk.Label(frm, text=label)
        caption.grid(row=i, column=0, sticky="w", pady=5)
        entry = ttk.Entry(frm, textvariable=paths[name])
        entry.grid(row=i, column=1, sticky="ew", padx=8)
        browse = ttk.Button(frm, text="Wybierz…", command=lambda n=name: choose(n, n == "output"))
        browse.grid(row=i, column=2)
        attach_tooltip(caption, FIELD_HELP[name])
        attach_tooltip(entry, FIELD_HELP[name])
        attach_tooltip(browse, BUTTON_HELP[name])

    ttk.Label(frm, text="Model Ollama").grid(row=4, column=0, sticky="w", pady=7)
    model_entry = ttk.Entry(frm, textvariable=model)
    model_entry.grid(row=4, column=1, sticky="ew", padx=8)
    attach_tooltip(model_entry, FIELD_HELP["model"])
    ttk.Label(frm, text="Zakres stron (puste = wszystkie)").grid(row=5, column=0, sticky="w", pady=7)
    pages_entry = ttk.Entry(frm, textvariable=pages)
    pages_entry.grid(row=5, column=1, sticky="ew", padx=8)
    attach_tooltip(pages_entry, FIELD_HELP["pages"])
    ttk.Label(frm, text="Rodzaj tekstu").grid(row=6, column=0, sticky="w", pady=7)
    mode_select = ttk.Combobox(frm, textvariable=mode, values=["handwriting", "all"], state="readonly")
    mode_select.grid(row=6, column=1, sticky="w", padx=8)
    attach_tooltip(mode_select, FIELD_HELP["mode"])
    ttk.Label(frm, text="Liczba pasów na stronę").grid(row=7, column=0, sticky="w", pady=7)
    segments_select = ttk.Combobox(frm, textvariable=segments, values=[1, 2, 3, 4, 5, 6], state="readonly", width=8)
    segments_select.grid(row=7, column=1, sticky="w", padx=8)
    attach_tooltip(segments_select, FIELD_HELP["segments"])
    ttk.Label(frm, text="Maksymalny bok renderu (px)").grid(row=8, column=0, sticky="w", pady=7)
    size_entry = ttk.Entry(frm, textvariable=max_side, width=12)
    size_entry.grid(row=8, column=1, sticky="w", padx=8)
    attach_tooltip(size_entry, FIELD_HELP["max_side"])
    ttk.Label(frm, text="Profil kompresji PDF").grid(row=9, column=0, sticky="w", pady=7)
    compression_select = ttk.Combobox(frm, textvariable=compression_profile,
                 values=["lossless", "light", "medium", "strong"],
                 state="readonly", width=14)
    compression_select.grid(row=9, column=1, sticky="w", padx=8)
    searchable_check = ttk.Checkbutton(frm, text="Zapisz przeszukiwalne PDF-y z warstwą HTR",
                                       variable=searchable_pdf)
    searchable_check.grid(row=10, column=0, columnspan=3, sticky="w", pady=7)
    attach_tooltip(compression_select, FIELD_HELP["compression"])
    attach_tooltip(searchable_check, FIELD_HELP["searchable"])
    ttk.Label(frm, text="Najedź kursorem na element, aby zobaczyć opis. Przetwarzanie wyłącznie lokalne.",
              foreground="#32624d").grid(row=11, column=0, columnspan=3, sticky="w", pady=8)
    log = tk.Text(frm, height=10, state="disabled", wrap="word")
    log.grid(row=13, column=0, columnspan=3, sticky="nsew", pady=8)
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(13, weight=1)
    bar = ttk.Frame(frm)
    bar.grid(row=12, column=0, columnspan=3, sticky="w")

    def append(message):
        log.configure(state="normal")
        log.insert("end", message + "\n")
        log.see("end")
        log.configure(state="disabled")

    def worker(config: Config):
        try:
            compare_documents(config, progress=lambda m: events.put(("log", m)), stop=stop)
            if stop.is_set():
                raise Cancelled("Analizę anulowano.")
            events.put(("complete", str(config.output / "report.html")))
        except Cancelled as exc:
            events.put(("cancelled", str(exc)))
        except Exception as exc:
            events.put(("error", str(exc)))

    def start():
        nonlocal is_running
        if is_running:
            return
        try:
            config = Config(
                original=Path(paths["original"].get()).expanduser(),
                compressed=Path(paths["compressed"].get()).expanduser(),
                output=Path(paths["output"].get()).expanduser(),
                reference=Path(paths["reference"].get()).expanduser() if paths["reference"].get() else None,
                model=model.get().strip(), mode=mode.get(), segments=segments.get(),
                max_side=int(max_side.get()), pages=pages.get().strip(),
                searchable_pdf=searchable_pdf.get())
            if not str(paths["original"].get()).strip() or not str(paths["compressed"].get()).strip():
                raise ValueError("Wybierz oba pliki PDF.")
            if not str(paths["output"].get()).strip():
                raise ValueError("Wybierz folder raportu.")
            if config.reference and not config.reference.is_file():
                raise ValueError("Nie znaleziono pliku TXT z transkrypcją wzorcową.")
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Błędne ustawienia", str(exc))
            return
        stop.clear()
        is_running = True
        btn_start.configure(state="disabled")
        btn_compress.configure(state="disabled")
        btn_stop.configure(state="normal")
        append("---- Nowa analiza ----")
        threading.Thread(target=worker, args=(config,), daemon=True).start()

    def compress_worker(source: Path, destination: Path, profile: str):
        try:
            from pdf_tools import compress_pdf
            stats = compress_pdf(source, destination, profile,
                                 progress=lambda m: events.put(("log", m)))
            events.put(("compression_complete", (str(destination), stats)))
        except Exception as exc:
            events.put(("error", str(exc)))

    def start_compress():
        nonlocal is_running
        if is_running:
            return
        source = Path(paths["original"].get()).expanduser()
        if not source.is_file():
            messagebox.showerror("Błąd", "Wybierz najpierw oryginalny PDF.")
            return
        target = filedialog.asksaveasfilename(title="Zapisz skompresowany PDF",
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=f"{source.stem}_{compression_profile.get()}.pdf")
        if not target:
            return
        is_running = True
        btn_start.configure(state="disabled")
        btn_compress.configure(state="disabled")
        append("---- Kompresja PDF ----")
        threading.Thread(target=compress_worker,
                         args=(source, Path(target), compression_profile.get()), daemon=True).start()

    def cancel():
        if not is_running:
            return
        btn_stop.configure(state="disabled")
        stop.set()
        append("Wysłano anulowanie: zamknięto aktywne połączenie z modelem.")

    def poll():
        nonlocal is_running
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "log":
                    append(value)
                else:
                    is_running = False
                    btn_start.configure(state="normal")
                    btn_compress.configure(state="normal")
                    btn_stop.configure(state="disabled")
                    if kind == "compression_complete":
                        location, stats = value
                        paths["compressed"].set(location)
                        append(f"Kompresja zakończona: {location}; {stats['source_bytes']} → {stats['output_bytes']} B; obrazy JPEG: {stats['images_reencoded']}.")
                        messagebox.showinfo("Gotowe", f"Zapisano PDF:\n{location}")
                        continue
                    append(value)
                    if kind == "complete":
                        messagebox.showinfo("Gotowe", f"Zapisano raport:\n{value}")
                    elif kind == "cancelled":
                        append("Anulowano analizę. Zakończone strony zachowano w checkpoint.")
                    elif kind == "error":
                        messagebox.showerror("Błąd", value)
        except queue.Empty:
            pass
        root.after(150, poll)

    btn_compress = ttk.Button(bar, text="Kompresuj oryginalny PDF", command=start_compress)
    btn_compress.pack(side="left", padx=(0, 9))
    btn_start = ttk.Button(bar, text="Rozpocznij HTR i porównanie", command=start)
    btn_start.pack(side="left", padx=(0, 9))
    btn_stop = ttk.Button(bar, text="Zatrzymaj", command=cancel, state="disabled")
    btn_stop.pack(side="left")
    attach_tooltip(btn_compress, BUTTON_HELP["compress"])
    attach_tooltip(btn_start, BUTTON_HELP["start"])
    attach_tooltip(btn_stop, BUTTON_HELP["stop"])
    root.after(150, poll)
    root.mainloop()


def cli() -> None:
    p = argparse.ArgumentParser(description="Porównanie lokalnego HTR dwóch PDF-ów. Bez argumentów: okno GUI.")
    p.add_argument("--original", type=Path, help="Oryginalny PDF")
    p.add_argument("--compressed", type=Path, help="Skompresowany PDF")
    p.add_argument("--output", type=Path, default=Path("htr_results"), help="Folder raportu")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--mode", choices=list(PROMPTS), default="handwriting", help="handwriting: tylko ręczne; all: wszystko")
    p.add_argument("--segments", type=int, default=2, help="Pasy na stronę (1–6)")
    p.add_argument("--max-side", type=int, default=2800, help="Maksymalny bok obrazu strony w px")
    p.add_argument("--pages", default="", help="Np. 1-3,5; puste: wszystkie")
    p.add_argument("--reference", type=Path, help="Opcjonalny TXT z referencją === PAGE N ===")
    p.add_argument("--compress", choices=["lossless", "light", "medium", "strong"],
                   help="Utwórz skompresowany PDF z --original (wyjście: --compressed)")
    p.add_argument("--compress-only", action="store_true", help="Kompresuj bez uruchamiania HTR/Ollama")
    p.add_argument("--no-searchable-pdf", action="store_true",
                   help="Nie twórz PDF-ów z niewidoczną warstwą OCR")
    args = p.parse_args()
    if args.original is None and args.compressed is None and not args.compress:
        run_gui()
        return
    if args.compress_only and not args.compress:
        p.error("--compress-only wymaga podania --compress.")
    if args.original is None:
        p.error("Podaj --original.")
    if not args.compress and args.compressed is None:
        p.error("Podaj --compressed albo wybierz --compress.")
    if args.compress:
        from pdf_tools import compress_pdf
        if args.compressed is None:
            args.compressed = args.output / f"{args.original.stem}_{args.compress}.pdf"
        try:
            print(compress_pdf(args.original, args.compressed, args.compress, progress=print))
        except (OSError, ValueError, RuntimeError) as exc:
            p.exit(2, f"Błąd kompresji: {exc}\n")
        if args.compress_only:
            return
    config = Config(original=args.original, compressed=args.compressed, output=args.output,
                    model=args.model, mode=args.mode, segments=args.segments,
                    max_side=args.max_side, pages=args.pages, reference=args.reference,
                    searchable_pdf=not args.no_searchable_pdf)
    try:
        result = compare_documents(config, progress=print)
        print("Rozbieżność HTR (znaki):", format_pct(result["summary"]["char_disagreement"]))
        print("Raport:", config.output / "report.html")
    except (OSError, ValueError, RuntimeError, Cancelled) as exc:
        p.exit(2, f"Błąd: {exc}\n")


if __name__ == "__main__":
    cli()
