# Interfejs graficzny

Okno Tkinter służy do wyboru źródeł, ustawienia kompresji i uruchomienia analizy. W wersji **1.2.0** każda akcja oraz główne pole ustawień mają **podpowiedź kontekstową (tooltip)**.

Podpowiedź pojawia się po około **550 ms** bez ruchu kursora nad kontrolką, a znika po opuszczeniu kontrolki lub kliknięciu. Pojawia się również po ustawieniu fokusu klawiaturą. Nie wymaga połączenia sieciowego.

## Przyciski

| Przycisk | Działanie |
| --- | --- |
| **Wybierz…** obok oryginału | Otwiera selektor pliku wejściowego PDF; oryginał nie jest nadpisywany. |
| **Wybierz…** obok drugiego PDF | Wskazuje dokument przeznaczony do porównania HTR. |
| **Wybierz…** obok TXT | Opcjonalnie wskazuje ręczną transkrypcję wzorcową do oceny CER/WER. |
| **Wybierz…** obok folderu | Wskazuje katalog raportów i wygenerowanych plików. |
| **Kompresuj oryginalny PDF** | Zapisuje drugi PDF wybranym profilem i ustawia go jako wejście porównawcze. Działa bez Ollama. |
| **Rozpocznij HTR i porównanie** | Uruchamia rozpoznanie obu PDF-ów, metryki i raport; wymaga modelu lokalnego. |
| **Zatrzymaj** | Przerywa po bieżącym wywołaniu modelu; ukończone strony pozostają we wznowieniu. |

## Ustawienia

| Pole | Znaczenie |
| --- | --- |
| Model Ollama | Nazwa lokalnego modelu, domyślnie `qwen3-vl:4b`. |
| Zakres stron | Puste = wszystkie; np. `1-3,5` = strony 1, 2, 3 i 5. |
| Rodzaj tekstu | `handwriting` = tylko ręczny; `all` = także drukowany. |
| Liczba pasów | 1–6 poziomych fragmentów strony; więcej pasów to więcej wywołań modelu. |
| Maksymalny bok renderu | Długość najdłuższego boku obrazu przekazanego do modelu, w px. |
| Profil kompresji | `lossless`, `light`, `medium`, `strong`. |
| Zapisz przeszukiwalne PDF-y | Dodaje po analizie niewidoczną warstwę HTR do kopii obu PDF-ów. |

## Typowy przebieg

1. Wybierz `PDF oryginalny` oraz folder raportu.
2. Wybierz `Profil kompresji PDF` i uruchom **Kompresuj oryginalny PDF**, albo wskaż istniejący drugi plik.
3. Ustaw tryb `handwriting`; dla drobnych odpowiedzi rozważ 3 pasy.
4. Opcjonalnie wskaż referencję TXT i zaznacz zapis przeszukiwalnych PDF-ów.
5. Kliknij **Rozpocznij HTR i porównanie**. Postęp widać w dolnym dzienniku.

Zobacz [raporty](results.md) i [metodologię](evaluation.md).
