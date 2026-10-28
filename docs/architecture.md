# Architektura projektu

## Główne moduły

| Plik | Odpowiedzialność |
| --- | --- |
| `htr_compare.py` | GUI Tkinter, CLI, integracja Ollama, segmentacja, OCR/HTR, porównanie, raporty, checkpoint. |
| `gui_tooltips.py` | Opisy kontrolek, opóźnione podpowiedzi po najechaniu i po uzyskaniu fokusu. |
| `pdf_tools.py` | Kompresja PDF, ponowne kodowanie obrazów, zapis niewidocznej warstwy Unicode. |
| `run.sh`, `run.cmd`, `run.ps1` | Platformowe skrypty startowe dla Linux/macOS i Windows. |
| `scripts/bootstrap.py` | Wykrywanie platformy, instalacja zależności i sprawdzanie Ollama. |
| `tests/` | Testy jednostkowe i integracyjne bez rzeczywistego modelu Ollama. |
| `docs/` + `mkdocs.yml` | Źródła dokumentacji MkDocs. |
| `.github/workflows/pages.yml` | Budowanie dokumentacji i publikacja przez GitHub Actions. |

## Granice systemu

```mermaid
flowchart TD
    GUI[GUI Tkinter / CLI] --> CORE[htr_compare.py]
    GUI --> COMP[pdf_tools.py - kompresja]
    GUI --> TIP[gui_tooltips.py]
    CORE --> PDF[pdf_tools.py - OCR PDF]
    CORE --> OLLAMA[Ollama localhost:11434]
    CORE --> REPORT[HTML CSV JSON TXT]
    COMP --> INPUT[Pliki PDF lokalne]
    PDF --> INPUT
```

## Ograniczenia

- Brak segmentacji pól odpowiedzi opartej na ich rzeczywistych granicach; używane są pasy poziome.
- Brak bounding boxów słów i wyrównywania tekstu do pikseli źródłowych.
- Niepełna obsługa niektórych typów obrazów PDF; nieobsługiwane obrazy pozostają niezmodyfikowane.
- Wyliczenie CER/WER wymaga opcjonalnej referencji tekstowej.
- Nie zawiera wbudowanego zbioru referencyjnego.

Potencjalne rozszerzenia techniczne: lokalizacja słów i wyrównanie obrazu.


## Transport i anulowanie

`ollama_transport.py` otwiera lokalne połączenie strumieniowe HTTP i agreguje porcje JSON. `CancelToken` przechowuje aktywne gniazdo TCP i pozwala je zamknąć z wątku interfejsu. Przerwany strumień nie może być potraktowany jako ukończona transkrypcja.
