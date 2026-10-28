# Instalacja

## Wymagania

- Linux (np. Fedora) z Pythonem 3.10+ i Tkinter do GUI; tryb CLI nie wymaga serwera wyświetlania.
- Biblioteki Python: PyMuPDF i Pillow (instalowane przez `run.sh`).
- Lokalna [Ollama](https://ollama.com/download/linux) i model `qwen3-vl:4b` dla HTR.
- Czcionka DejaVu Sans dla poprawnego eksportu polskich znaków w przeszukiwalnym PDF.
- Odpowiednia pamięć RAM/VRAM do wybranego modelu. Bez GPU rozpoznawanie może być wolne.

## Fedora

```bash
sudo dnf install git python3 python3-pip python3-tkinter dejavu-sans-fonts
ollama pull qwen3-vl:4b
ollama list
git clone https://github.com/MatPomGit/htr-ocr-pdf.git
cd htr-ocr-pdf
./run.sh
```

Ollama powinna działać lokalnie pod adresem `http://127.0.0.1:11434`. Gdy nie działa jako usługa, uruchom `ollama serve` w oddzielnym terminalu.

`run.sh` tworzy środowisko `.venv` i instaluje zależności aplikacji. Pierwsze uruchomienie wymaga dostępu do PyPI; dalsze przetwarzanie dokumentów odbywa się lokalnie.

## CLI bez GUI

```bash
./run.sh --original original.pdf --compressed compressed.pdf --output wyniki --segments 3
```

Aby przetestować kompresję bez Ollama:

```bash
./run.sh --original original.pdf --compressed medium.pdf --compress medium --compress-only
```

Zobacz [opis profili kompresji](compression.md) i [diagnozowanie problemów](troubleshooting.md).
