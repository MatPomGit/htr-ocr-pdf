# Rozwój, testowanie i publikacja

## Uruchomienie testów

```bash
python3 -m unittest discover -s tests -v
```

Testy kontrolują logikę HTR, raporty, kompresję i eksport tekstu oraz podpowiedzi GUI bez wymagania okna graficznego. Oddzielnie trzeba wykonywać testy manualne na komputerze z Tkinter i lokalnym modelem Ollama.

## Dokumentacja lokalnie

```bash
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r requirements-docs.txt
.venv-docs/bin/python -m mkdocs serve
```

Otwórz lokalny adres wskazany przez MkDocs. Sprawdzenie ścisłe:

```bash
.venv-docs/bin/python -m mkdocs build --strict
```

## GitHub Pages

Workflow `.github/workflows/pages.yml`:

1. Przy zmianie dokumentacji w PR wykonuje `mkdocs build --strict`.
2. Po scaleniu do `main` buduje stronę i przesyła artefakt GitHub Pages.
3. Wdraża artefakt na `https://matpomgit.github.io/htr-ocr-pdf/`.

!!! important "Jednorazowe ustawienie GitHub Pages"
    Jeżeli Pages nie jest jeszcze aktywne, właściciel repozytorium musi wybrać w **Settings → Pages → Build and deployment → Source: GitHub Actions**. Token `GITHUB_TOKEN` w workflow nie może samodzielnie włączyć GitHub Pages. Po aktywacji workflow publikuje kolejne aktualizacje automatycznie.

## Zasady rozwoju

- Najpierw wykonuj zmiany w osobnej gałęzi/PR.
- Utrzymuj zgodność CLI i GUI.
- Nie wysyłaj materiałów studenckich do zewnętrznych modeli.
- Nie zastępuj automatycznie archiwalnych PDF-ów skompresowaną kopią.
- Dla nowych parametrów dodawaj testy i aktualizuj dokumentację.
