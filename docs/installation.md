# Instalacja i uruchomienie

HTR OCR PDF korzysta ze wspólnego instalatora `scripts/bootstrap.py`, uruchamianego
przez platformowe skrypty. Instalator korzysta ze standardowej biblioteki Python,
dlatego przed utworzeniem środowiska wirtualnego nie potrzebuje dodatkowych pakietów.

## Obsługiwane systemy

| System | Skrypt | Menedżer zależności systemowych |
| --- | --- | --- |
| Fedora / RHEL | `./run.sh` | DNF |
| Debian / Ubuntu / Mint | `./run.sh` | APT |
| Arch / Manjaro | `./run.sh` | pacman |
| openSUSE | `./run.sh` | zypper |
| Alpine | `./run.sh` | apk |
| macOS | `./run.sh` | Homebrew (jeśli jest zainstalowany) |
| Windows 10/11 | `run.cmd` lub `run.ps1` | winget (jeśli jest zainstalowany) |

Python 3.10+ jest wymaganiem uruchomienia instalatora; gdy nie jest dostępny,
należy go zainstalować narzędziem systemowym przed pierwszym uruchomieniem.

## Automatyczne doinstalowanie

Na pierwszym uruchomieniu program:

1. Rozpoznaje system, dystrybucję i menedżer pakietów.
2. Sprawdza Tkinter i czcionkę Unicode (gdy potrzebne).
3. Przy brakach proponuje konkretne polecenie do zatwierdzenia; uprawnienia
   administratora są uzyskiwane wyłącznie przez standardowe `sudo`, gdy wymagane.
4. Tworzy `.venv` i instaluje PyMuPDF i Pillow z `requirements.txt`.
5. W trybie HTR sprawdza lokalną Ollama, w razie potrzeby proponuje jej instalację,
   uruchamia serwer lokalny i proponuje pobranie `qwen3-vl:4b`.
6. Przekazuje oryginalne argumenty do `htr_compare.py`.

Instalator ponawia konfigurację brakującego `python3-venv` na dystrybucjach
z osobnym pakietem. Zależności Python są instalowane w katalogu projektu, nigdy
do globalnego Pythona. Przy niezmienionym `requirements.txt` i poprawnych
importach nie wykonuje ponownej instalacji pakietów.

### Uruchomienie

```bash
# Linux i macOS
./run.sh
./run.sh --setup
./run.sh --doctor
```

```powershell
# Windows
.\run.cmd
.\run.cmd --setup
.\run.cmd --doctor
```

`--doctor` zwraca diagnostykę JSON bez wykonywania instalacji. Przykłady
trybów uruchomienia:

```bash
./run.sh --setup --yes                # automatyczne zaakceptowanie zmian
./run.sh --setup --no-system          # bez instalacji pakietów systemowych
./run.sh --setup --no-ollama          # bez pobierania silnika i modelu
./run.sh --bootstrap-help             # pomoc instalatora
./run.sh --original a.pdf --compressed b.pdf --compress medium --compress-only
```

## Model i bezpieczeństwo instalacji

Model jest pobierany tylko po zatwierdzeniu, ponieważ może zajmować kilka GB.
Brak modelu nie blokuje funkcji kompresji PDF. Instalacja Ollama jest wykonywana
przez menedżer pakietów, jeśli udostępnia odpowiedni pakiet; dla systemów
bez takiego źródła instalator wskazuje oficjalną stronę
[Ollama](https://ollama.com/download). Żadne `curl | sh`, `irm | iex`
ani zewnętrzne skrypty instalacyjne nie są automatycznie uruchamiane.

Komponenty wymagające uprawnień administratora nie są instalowane bez
potwierdzenia. W trybie nieinteraktywnym brak potwierdzenia powoduje pominięcie
takiej operacji i komunikat diagnostyczny.

Na Windows obsługa Tkinter jest zwykle częścią instalatora Python; jeśli jej
brakuje, należy poprawić instalację Pythona z opcją Tcl/Tk. Na macOS z Pythonem
Homebrew instalator może użyć pakietu `python-tk@X.Y` odpowiedniego dla wersji
interpretera. Czcionka jest wyszukiwana w standardowych katalogach systemu.

## Testy instalatora

```bash
python3 -m unittest discover -s tests -p "test_bootstrap.py" -v
```

Testy nie wykonują instalacji i nie pobierają modelu. Testowane są osobno
na Windows, macOS i Ubuntu przez GitHub Actions.

Zobacz [rozwiązywanie problemów](troubleshooting.md).
