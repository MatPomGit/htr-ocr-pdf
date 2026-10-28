"""Nienachalne podpowiedzi kontekstowe dla interfejsu Tkinter.

Bez zależności zewnętrznych. Nie tworzy dodatkowego okna, dopóki
użytkownik nie zatrzyma kursora lub nie ustawi fokusu na kontrolce.
"""
from __future__ import annotations


BUTTON_HELP = {
    "original": "Wskaż niezmieniony plik źródłowy PDF. Program nigdy go nie nadpisuje.",
    "compressed": "Wskaż drugi PDF do porównania. Możesz go również utworzyć przyciskiem kompresji.",
    "reference": (
        "Wybierz opcjonalny plik TXT UTF-8 z ręcznie sprawdzoną transkrypcją. "
        "Dzięki temu program obliczy rzeczywisty CER i WER. "
        "Dla wielu stron użyj nagłówków === PAGE N ===."
    ),
    "output": "Wybierz folder na raport HTML, transkrypcje, wyniki CSV/JSON i przeszukiwalne PDF-y.",
    "compress": (
        "Utwórz drugi PDF z pliku oryginalnego, używając wybranego profilu. "
        "Kompresja działa bez modelu Ollama, a plik wynikowy zostanie automatycznie "
        "wskazany do porównania. Oryginał pozostaje bez zmian."
    ),
    "start": (
        "Rozpocznij lokalne HTR obu dokumentów i porównaj wyniki. "
        "Wymaga uruchomionej Ollama z pobranym modelem. "
        "Zapisuje raport, transkrypcje i opcjonalną warstwę OCR w PDF."
    ),
    "stop": (
        "Anuluj bieżące żądanie HTR do Ollama przez zamknięcie połączenia, "
        "bez oczekiwania na wygenerowanie całej odpowiedzi. "
        "Ukończone strony pozostają w checkpoint i mogą być wznowione."
    ),
}

FIELD_HELP = {
    "original": BUTTON_HELP["original"],
    "compressed": BUTTON_HELP["compressed"],
    "reference": BUTTON_HELP["reference"],
    "output": BUTTON_HELP["output"],
    "model": "Nazwa lokalnego modelu Ollama, domyślnie qwen3-vl:4b. Model musi być wcześniej pobrany.",
    "pages": "Puste pole oznacza wszystkie strony. Przykłady: 1, 2-4 lub 1-3,7.",
    "mode": (
        "handwriting: rozpoznaj wyłącznie pismo odręczne; all: tekst drukowany i odręczny. "
        "Tryb all może powielać tekst obecny już w PDF."
    ),
    "segments": (
        "Podział każdej strony na 1–6 poziomych pasów. Więcej pasów ułatwia odczyt "
        "drobnego pisma, ale wydłuża pracę i może przeciąć wyrazy."
    ),
    "max_side": (
        "Najdłuższy bok obrazu przekazywanego do HTR, w pikselach. "
        "Większa wartość zwiększa szczegółowość, ale zużywa więcej pamięci."
    ),
    "compression": (
        "lossless: optymalizacja bez zmiany pikseli; light: JPEG 88 / 100%; "
        "medium: JPEG 72 / 85%; strong: JPEG 50 / 70% rozdzielczości obrazów. "
        "Kompresja nie zmienia drukowanego tekstu wektorowego."
    ),
    "searchable": (
        "Po HTR dodaj niewidoczną warstwę tekstu do kopii obu PDF-ów. "
        "Umożliwia wyszukiwanie i kopiowanie, ale pozycje znaków są przybliżone."
    ),
}


class Tooltip:
    """Podpowiedź po zatrzymaniu kursora lub skupieniu klawiaturą."""

    def __init__(self, widget, text: str, delay_ms: int = 550):
        self.widget = widget
        self.text = text.strip()
        self.delay_ms = delay_ms
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<FocusIn>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        if not self._tip and self.text:
            self._job = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except (RuntimeError, ValueError):
                pass
            self._job = None

    def _show(self):
        self._job = None
        if self._tip is not None or not self.widget.winfo_exists():
            return
        import tkinter as tk

        popup = tk.Toplevel(self.widget)
        popup.withdraw()
        popup.overrideredirect(True)
        label = tk.Label(
            popup, text=self.text, justify="left", anchor="w",
            background="#fffde9", foreground="#1f2937", relief="solid",
            borderwidth=1, padx=9, pady=7, wraplength=400,
            font=("TkDefaultFont", 10),
        )
        label.pack()
        popup.update_idletasks()
        x, y = self.widget.winfo_pointerxy()
        x = max(0, min(x + 16, popup.winfo_screenwidth() - popup.winfo_reqwidth() - 8))
        y = max(0, min(y + 18, popup.winfo_screenheight() - popup.winfo_reqheight() - 8))
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        self._tip = popup

    def _hide(self, _event=None):
        self._cancel()
        if self._tip is not None:
            tip, self._tip = self._tip, None
            try:
                tip.destroy()
            except (RuntimeError, ValueError):
                pass


def attach_tooltip(widget, text: str) -> Tooltip:
    """Powiąż podpowiedź z elementem GUI; zwróć uchwyt do testów."""
    return Tooltip(widget, text)
