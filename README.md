# HTR PDF Compare 1.2.1

Lokalne porównanie odczytu pisma odręcznego z dwóch PDF-ów (oryginału i wersji skompresowanej). GUI Tkinter i CLI. Żadnego płatnego API ani wysyłania skanów do usług chmurowych. Dwa pliki są renderowane z tymi samymi parametrami, a identyczne regiony strony rozpoznaje **ten sam model**.

**Dokumentacja MkDocs:** [matpomgit.github.io/htr-ocr-pdf](https://matpomgit.github.io/htr-ocr-pdf/) (po uruchomieniu GitHub Pages); źródła: [docs/](docs/index.md).

Wersja 1.2.0 dodaje kontekstowe podpowiedzi po najechaniu na przyciski, pola plików i ustawienia GUI. Po około 550 ms pojawia się opis działania elementu; podpowiedzi są też dostępne po ustawieniu fokusu klawiaturą. Implementacja: `gui_tooltips.py`.

## Instalacja (Fedora)

1. Zainstaluj [Ollama](https://ollama.com/download/linux), uruchom usługę i pobierz model:

   ```bash
   ollama pull qwen3-vl:4b
   ollama list
   ```

   Qwen3-VL wymaga Ollama co najmniej 0.12.7. Model `qwen3-vl:4b` zajmuje około 3,3 GB na dysku, dodatkowa pamięć jest potrzebna do działania. Bez GPU uruchomienie może być wolne.

2. Zainstaluj GUI i venv:

   ```bash
   sudo dnf install python3-tkinter python3-pip
   ```

3. W rozpakowanym folderze uruchom:

   ```bash
   ./run.sh
   ```

   Przy pierwszym uruchomieniu `run.sh` instaluje Pythonowe pakiety `PyMuPDF` i `Pillow` z PyPI. Następnie przetwarzanie dokumentów i rozpoznawanie jest lokalne.

## Użycie

W GUI wybierz dwa PDF-y i folder raportu. Domyślnie rozpoznawane jest tylko pismo **odręczne** (`handwriting`); druk formularza jest pomijany. Można wybrać `all` (tekst drukowany i ręczny). Dla drobnego pisma ustaw 3–4 pasy strony; większa liczba pasów zwiększa liczbę zapytań, ale może ułatwić rozpoznawanie. Podział na pasy jest wybierany z obszarów o najmniejszej ilości ciemnych pikseli blisko równych części strony i wspólny dla obu wersji.

CLI, najpierw test pierwszej strony:

```bash
./run.sh --original ~/Pobrane/original.pdf \
  --compressed ~/Pobrane/compressed.pdf \
  --output ~/Pobrane/htr_comparison --pages 1 --segments 2
```

Wszystkie strony i 3 pasy:

```bash
./run.sh --original ~/Pobrane/original.pdf \
  --compressed ~/Pobrane/compressed.pdf \
  --output ~/Pobrane/htr_comparison --segments 3
```

## Opcjonalny pomiar dokładności: prawdziwy CER/WER

Aby zmierzyć dokładność, dodaj transkrypcję wykonaną **przez człowieka** w UTF-8, np. `reference.txt`:

```text
=== PAGE 1 ===
Pierwszy fragment tekstu
Drugi fragment tekstu

=== PAGE 2 ===
Tekst odręczny z drugiej strony
```

W trybie `handwriting` plik wzorcowy powinien zawierać **wyłącznie** pismo odręczne, bez drukowanych pytań. Wzorzec może obejmować tylko wybrane strony. `--reference reference.txt` (lub wskazanie pliku w GUI) dodaje rzeczywisty CER i WER względem wzorca.

Bez wzorca program liczy wyłącznie **rozbieżność transkrypcji** między plikami (symetryczny Levenshtein, mianownik = maksymalna długość obu transkrypcji), nie dokładność HTR. Dwie jednakowo błędne transkrypcje mogą mieć rozbieżność równą 0%. Nie należy na tej podstawie stwierdzać braku wpływu kompresji na prawidłowość OCR/HTR.

W razie przerwania zadania program zapisuje `checkpoint.json` po każdej ukończonej stronie i wznawia analizę od ostatniego zakończonego etapu, o ile nie zmieniły się pliki, model ani parametry.

## Pliki wynikowe

- `report.html` — czytelny raport porównujący tekst strony po stronie.
- `original_htr.txt`, `compressed_htr.txt` — transkrypcje.
- `metrics.csv` — rozbieżność CER/WER, RMSE, PSNR oraz CER/WER względem wzorca (jeśli podany).
- `results.json` — komplet danych, rozdzielczości renderowania, SHA-256 plików, model (wraz z identyfikatorem digest) i parametry.

## Ograniczenia i ostrożność

- Qwen3-VL jest ogólnym modelem multimodalnym. Może pomijać fragmenty tekstu, dopisywać treść lub mylić druk z rękopisem.
- Rozpoznawanie pełnych stron może być mniej dokładne niż odpowiednio wydzielonych pól odpowiedzi. Liczba pasów to kompromis. Granice pasów mogą przeciąć tekst, szczególnie przy dużych rysunkach lub nieregularnym układzie.
- Model może nieprawidłowo rozpoznawać polskie znaki, równania i symbole matematyczne. Rozpoznanie tekstu może zawierać błędy.
- Każde ponowne uruchomienie modelu może nieznacznie zmienić wynik mimo temperatury 0. Powtarzalność wymaga kontroli wersji modelu, ustawień i danych wejściowych.
- Wymagana jest ta sama liczba stron i zbliżone rozmiary geometryczne obu PDF-ów. Nie wykonujemy automatycznej rejestracji (alignment) przesuniętych skanów.
- Pixele z każdego PDF-a mogą się nieznacznie różnić także na skutek renderowania. PSNR i RMSE dotyczą renderowanych stron, a nie surowych danych JPEG w PDF.
- Dane wejściowe i raporty pozostają lokalne. Nie są przesyłane do zewnętrznych usług.
- Na stronie o niezwykłym fizycznym rozmiarze (np. 1987×2761 pt), parametr `--max-side` ogranicza faktyczny rozmiar wejścia modelu, a DPI wyliczane jest automatycznie. Domyślnie 2800 px, z możliwością zwiększenia.

## Testy bez Ollama

```bash
python3 -m unittest discover -s tests -v
```


## Kompresja PDF i przeszukiwalne PDF-y (1.1.0)

W GUI wybierz **PDF oryginalny**, ustaw profil i kliknij **Kompresuj oryginalny PDF**. Zapisany dokument zostanie automatycznie wskazany jako drugi PDF do porównania HTR. Kompresja działa niezależnie od Ollama.

| Profil | Mechanizm | Parametry |
| --- | --- | --- |
| `lossless` | Optymalizacja struktury, kompresja strumieni, usuwanie nieużywanych obiektów | Bez zmian pikseli obrazów |
| `light` | Ponowne kodowanie obsługiwanych obrazów jako JPEG | Jakość 88, bez zmiany rozdzielczości |
| `medium` | JPEG z redukcją rozdzielczości obrazów | Jakość 72, 85% wymiarów obrazu |
| `strong` | Mocniejsze kodowanie JPEG i redukcja obrazów | Jakość 50, 70% wymiarów obrazu |

Kompresor **nie rasteryzuje całych stron**. Tekst drukowany i grafika wektorowa zachowują strukturę PDF. Nieobsługiwane lub maskowane obrazy są pomijane. JPEG zastępuje osadzony obraz tylko wtedy, gdy plik obrazu staje się mniejszy. Profil bezstratny może zmniejszyć rozmiar, ale nie gwarantuje oszczędności; ponowny zapis PDF może unieważnić podpisy cyfrowe. Zawsze zachowaj oryginał.

Samodzielna kompresja bez Ollama:

```bash
./run.sh --original original.pdf --compressed medium.pdf --compress medium --compress-only
```

Kompresja i porównanie HTR:

```bash
./run.sh --original original.pdf --compressed medium.pdf --compress medium --output results --segments 3
```

Po HTR program tworzy także `original_searchable.pdf` i `compressed_searchable.pdf`: oryginalny wygląd stron z niewidoczną, kopiowalną i przeszukiwalną warstwą tekstu HTR. Polska czcionka DejaVu Sans: `sudo dnf install dejavu-sans-fonts`. Lokalizacje tekstu są **przybliżone**, ponieważ model zwraca tekst pasów strony, a nie współrzędne słów; zaznaczenie wyników wyszukiwania nie musi odpowiadać dokładnemu położeniu pisma. Tryb `all` może zdublować istniejący tekst drukowany. Wyłączenie eksportu: `--no-searchable-pdf` lub odznaczenie opcji w GUI.

Kompresja i eksport odbywają się lokalnie. Poprawność transkrypcji zależy od jakości wejścia i modelu.


## Dokumentacja projektu (MkDocs)

```bash
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r requirements-docs.txt
.venv-docs/bin/python -m mkdocs serve
# Kontrola integralności na CI: .venv-docs/bin/python -m mkdocs build --strict
```

Strona jest automatycznie wdrażana przy zmianach dokumentacji na `main` przez `.github/workflows/pages.yml`. W nowym repozytorium może być wymagane jednorazowe wybranie `Settings → Pages → Source: GitHub Actions`.


## Anulowanie aktywnego HTR (1.2.1)

Przycisk **Zatrzymaj** zamyka aktywne strumieniowe połączenie z lokalnym Ollama. Nie czeka na ukończenie bieżącej generacji, nie przerywa innych zadań Ollama i nie usuwa ukończonych stron zapisanych w `checkpoint.json`. Niekompletna odpowiedź modelu jest odrzucana. Model może pozostawać załadowany w pamięci przez czas `keep_alive` bez generowania.
