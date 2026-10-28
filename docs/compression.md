# Kompresja PDF

Kompresor `pdf_tools.py` zapisuje **kopię** dokumentu, zachowując istniejący tekst oraz grafikę wektorową. W wariantach stratnych ponownie koduje tylko obsługiwane osadzone obrazy, bez rasteryzacji całych stron.

## Profile

| Profil | Kodowanie obrazów | Skala wymiarów bitmap |
| --- | --- | --- |
| `lossless` | Bez zmiany danych obrazowych; optymalizacja struktury PDF | 100% |
| `light` | JPEG, parametr jakości 88 | 100% |
| `medium` | JPEG, parametr jakości 72 | 85% |
| `strong` | JPEG, parametr jakości 50 | 70% |

Skala odnosi się do szerokości i wysokości obrazu, a nie do rozmiaru pliku PDF. Program koduje osadzony obraz tylko wtedy, kiedy zakodowane bajty zajmują mniej miejsca. Obrazy z maską przezroczystości i nieobsługiwane konstrukcje są pomijane.

!!! note "Bezstratny nie oznacza identycznego pliku"
    Profil `lossless` ma zachować piksele obrazów i zawartość stron, ale ponownie zapisuje strukturę PDF. Suma SHA-256 może się zmienić, a plik wynikowy nie musi być mniejszy. Ponowny zapis może też unieważnić podpis cyfrowy.

!!! warning "Nie zastępuj oryginału"
    JPEG jest stratny, nawet gdy rozdzielczość pozostaje taka sama. W zastosowaniach HTR mogą zanikać delikatne kropki, akcenty, łączenia liter oraz cienkie kreski ołówka. Oryginał należy zachować.

## Przykład CLI

```bash
./run.sh --original source.pdf --compressed source_medium.pdf \
  --compress medium --compress-only
```

Kompresja połączona z analizą HTR:

```bash
./run.sh --original source.pdf --compressed source_medium.pdf \
  --compress medium --output wyniki --segments 3
```

Wynik kompresji zawiera liczbę stron, liczbę przekodowanych i pominiętych obrazów oraz rozmiary wejściowy/wyjściowy. Zobacz [definicje metryk](evaluation.md).
