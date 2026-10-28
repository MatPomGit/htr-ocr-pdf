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

W razie potrzeby uruchom `ollama serve` i pobierz `qwen3-vl:4b`. Program nie dopuszcza połączeń do zdalnego serwera Ollama.

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


## Zatrzymanie HTR

Od wersji 1.2.1 przycisk **Zatrzymaj** zamyka aktywny strumień HTTP bez czekania na całą odpowiedź. Sprawdź wersję widoczną w tytule GUI. `ollama ps` może nadal pokazywać model, ponieważ `keep_alive` utrzymuje go w pamięci; nie oznacza to aktywnej generacji.
