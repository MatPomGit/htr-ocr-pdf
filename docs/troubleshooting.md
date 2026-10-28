# Rozwiązywanie problemów

## Nie otwiera się interfejs

Instalator próbuje wykryć Tkinter i odpowiedni pakiet systemowy. Jeśli brak dostępu do menedżera pakietów, wykonaj `./run.sh --doctor` (Windows: `run.cmd --doctor`). GUI wymaga aktywnej sesji graficznej; CLI jej nie wymaga.

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
./run.sh --setup
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


## Instalator nie może doinstalować pakietu

Uruchom `./run.sh --doctor` lub na Windows `run.cmd --doctor`.
Parametr `--setup` ponowi instalację; `--no-system` uniemożliwia zmianę pakietów
systemowych, a `--no-ollama` pomija instalację silnika. Jeśli nie ma interaktywnego
terminala, program nie podnosi uprawnień automatycznie. Menedżer APT może nie
posiadać pakietu Ollama; wówczas dostępna jest tylko instalacja oficjalna z
https://ollama.com/download.

## Błąd tworzenia środowiska .venv

Sprawdź wersję `python3 --version` (wymagane >= 3.10) oraz obecność
`python3-venv` na Debian/Ubuntu. Instalator spróbuje doinstalować ten
pakiet po zaakceptowaniu operacji. Zależności aplikacji nie są instalowane globalnie.

## Windows: polecenie python lub py nie istnieje

Zainstaluj Python 3.10+ (ze wsparciem Tcl/Tk) i udostępnij `py` albo
`python` w PATH. Następnie uruchom `run.cmd --setup`.
