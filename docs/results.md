# Raporty i przeszukiwalne PDF-y

Folder wskazany w GUI lub przez `--output` zawiera:

| Plik | Zawartość |
| --- | --- |
| `report.html` | Wizualne porównanie transkrypcji HTR, strona po stronie. |
| `original_htr.txt` | Transkrypcja oryginalnych stron, znaczniki `=== PAGE N ===`. |
| `compressed_htr.txt` | Transkrypcja po kompresji. |
| `metrics.csv` | Rozbieżność znakowa i słowna, RMSE, PSNR oraz CER/WER, jeśli jest wzorzec. |
| `results.json` | Dane stron, metryki, identyfikacja modelu, opcje i sumy SHA-256 wejść. |
| `original_searchable.pdf` | Kopia oryginału z niewidoczną warstwą rozpoznanych znaków. |
| `compressed_searchable.pdf` | Kopia drugiego PDF z niewidoczną warstwą HTR. |
| `checkpoint.json` | Częściowy stan podczas analizy; usuwany po pomyślnym zakończeniu. |

## Warstwa tekstowa OCR/HTR

Domyślnie program zachowuje widoczną zawartość strony i dodaje w PDF **niewidoczny** tekst z użyciem lokalnej czcionki Unicode DejaVu Sans. Pozwala to przeszukiwać i kopiować transkrypcję, mimo że skan pozostaje widoczny w niezmienionej postaci.

!!! warning "Pozycjonowanie jest przybliżone"
    Obecny model zwraca fragmenty tekstu z poziomych pasów, **nie** współrzędne liter i słów. Pozycje niewidocznej warstwy są rozkładane orientacyjnie w obrębie pasa; dokładne zaznaczanie tekstu i podświetlenia wyników wyszukiwania mogą nie odpowiadać rękopisowi.

Przy przetwarzaniu wybranych stron warstwa HTR jest dodawana tylko do nich, a pozostałe strony zostają zachowane. Domyślny tryb `handwriting` nie dodaje wydrukowanych pytań, których model nie transkrybuje.

Można wyłączyć tworzenie PDF z OCR przez `--no-searchable-pdf` albo odznaczyć odpowiednie pole w GUI.

## Odmienność metryk

`char_disagreement` z porównania dwóch transkrypcji **nie jest** równoważny `CER` względem zweryfikowanego wzorca. Zobacz [metodologię](evaluation.md).
