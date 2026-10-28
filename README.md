# HTR PDF Compare 1.0.0

Lokalne porównanie odczytu pisma odręcznego z dwóch PDF-ów (oryginału i wersji skompresowanej). GUI Tkinter i CLI. Żadnego płatnego API ani wysyłania skanów do usług chmurowych. Dwa pliki są renderowane z tymi samymi parametrami, a identyczne regiony strony rozpoznaje **ten sam model**.

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
Pierwsza ręczna odpowiedź studenta
Druga ręczna odpowiedź studenta

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

- To **pilotażowa aplikacja badawcza**. Qwen3-VL jest modelem ogólnego widzenia i języka, a nie zwalidowanym klinicznie/systemowo HTR. Może pomijać odręczne fragmenty, dopisywać treść lub mylić druk z rękopisem. Wyniki wymagają ręcznej oceny.
- Rozpoznawanie pełnych stron może być mniej dokładne niż odpowiednio wydzielonych pól odpowiedzi. Liczba pasów to kompromis. Granice pasów mogą przeciąć tekst, szczególnie przy dużych rysunkach lub nieregularnym układzie.
- Model może nieprawidłowo rozpoznawać polskie znaki, równania i symbole matematyczne. Przy ocenie studentów nie używaj transkrypcji jako jedynej podstawy decyzji.
- Każde ponowne uruchomienie modelu może nieznacznie zmienić wynik mimo temperatury 0. Do publikacji naukowej użyj kontroli powtórzeń, anotacji eksperckiej i protokołu ewaluacji.
- Wymagana jest ta sama liczba stron i zbliżone rozmiary geometryczne obu PDF-ów. Nie wykonujemy automatycznej rejestracji (alignment) przesuniętych skanów.
- Pixele z każdego PDF-a mogą się nieznacznie różnić także na skutek renderowania. PSNR i RMSE dotyczą renderowanych stron, a nie surowych danych JPEG w PDF.
- Dane studenckie i raporty pozostają lokalne; przed przekazaniem osobom trzecim należy zadbać o zgodność z zasadami ochrony danych.
- Na stronie o niezwykłym fizycznym rozmiarze (np. 1987×2761 pt), parametr `--max-side` ogranicza faktyczny rozmiar wejścia modelu, a DPI wyliczane jest automatycznie. Domyślnie 2800 px, z możliwością zwiększenia.

## Testy bez Ollama

```bash
python3 -m unittest discover -s tests -v
```
