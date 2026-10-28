# Rozwiązywanie problemów

## Nie otwiera się interfejs

Na Fedorze zainstaluj `python3-tkinter` i uruchamiaj aplikację w sesji z serwerem graficznym. Praca przez SSH bez przekazywania X11 wymaga użycia CLI.

## Nie pojawiają się podpowiedzi

Zatrzymaj wskaźnik nad przyciskiem/polem na około 0,55 s albo ustaw fokus klawiaturą. Podpowiedzi znikają po odsunięciu kursora, kliknięciu lub utracie fokusu. Nie są wyświetlane stale.

## Brak połączenia z Ollama

Sprawdź:

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
```

W razie potrzeby uruchom `ollama serve` i pobierz `qwen3-vl:4b`. Program blokuje zdalne adresy Ollama w celu ochrony skanów.

## Brak fontu do zapisu PDF

```bash
sudo dnf install dejavu-sans-fonts
```

Warstwa Unicode potrzebuje fontu obsługującego polskie znaki.

## Kompresja nie zmniejsza pliku

To możliwe zwłaszcza w trybie bezstratnym, dla wcześniej zoptymalizowanych PDF-ów albo gdy ponowne kodowanie pojedynczych obrazów nie daje oszczędności. Oryginał pozostaje bez zmian.

## Nieprecyzyjne podświetlanie wyszukiwania w PDF

Obecny model zwraca tekst segmentu, ale nie pozycje słów. Warstwa jest pozycjonowana przybliżenie. Rozwiązanie wymaga modelu OCR z bounding boxami lub algorytmu dopasowującego tekst do obrazu.

## Nie działa publikacja dokumentacji

Sprawdź Actions → **Documentation / GitHub Pages**. Jeżeli krok `Configure GitHub Pages` zgłasza, że Pages nie jest aktywne, ustaw w repozytorium **Settings → Pages → Source: GitHub Actions**. Pozostałe błędy kompilacji dokumentacji widoczne są w zadaniu `build`.
