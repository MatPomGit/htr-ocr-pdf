# Metodologia: wpływ kompresji na HTR

## Pytanie badawcze

Czy zmniejszenie rozmiaru skanu PDF pogarsza dokładność rozpoznawania pisma odręcznego, jeśli model i parametry przetwarzania pozostają niezmienione?

W porównywaniu dwóch PDF-ów należy utrzymywać stałe: model i digest, temperaturę, segmentację, rozmiar renderu, kolejność stron i sposób normalizacji tekstu.

## Rozbieżność bez wzorca

Dla transkrypcji oryginału `A` i wersji skompresowanej `B` używany jest dystans Levenshteina:

`char_disagreement = distance(A, B) / max(len(A), len(B))`

Analogicznie obliczana jest rozbieżność słowna. Wynik równy 0 nie dowodzi prawidłowości transkrypcji: oba wyniki mogą być jednakowo błędne.

## Rzeczywisty CER i WER

Dla ręcznie zweryfikowanej referencji `R` oraz predykcji `P`:

`CER = distance(R, P) / liczba_znaków(R)`

`WER = distance(tokeny(R), tokeny(P)) / liczba_słów(R)`

Rozbieżność między dokładnościami:

`delta_CER = CER_po_kompresji - CER_oryginału`

Wartości dodatnie oznaczają degradację jakości transkrypcji. Dla pustych referencji metryki mogą być niezdefiniowane.

### Referencja TXT

```text
=== PAGE 1 ===
odpowiedź odręczna pierwsza
odpowiedź odręczna druga

=== PAGE 2 ===
odpowiedź z kolejnej strony
```

Uruchomienie z transkrypcją wzorcową:

```bash
./run.sh --original original.pdf --compressed compressed.pdf \
  --reference reference.txt --mode handwriting --segments 3 --output wyniki
```

Referencja musi obejmować ten sam typ tekstu, co tryb rozpoznawania (w trybie `handwriting` tylko pismo ręczne).

## Metryki wizualne

Aplikacja mierzy RMSE i PSNR na wyrenderowanych stronach RGB, a nie na zakodowanych bajtach obrazów PDF. Zgodność wizualna nie musi przekładać się na zgodność wyników HTR, dlatego warto analizować CER/WER oraz błędy krytyczne (cyfry, symbole, diakrytyki).

## Zalecany pilotaż

Zgromadź reprezentatywną próbę odpowiedzi o różnej czytelności, w tym ołówkiem i ze znakami matematycznymi. Każdą odpowiedź porównaj z transkrypcją ekspercką. Analizuj zmiany CER/WER w parach, a nie wyłącznie na całym dokumencie. Osobno raportuj liczbę pominiętych i nieczytelnych odpowiedzi oraz powtórz HTR dla oceny stabilności modelu.

**Nie używaj automatycznego HTR jako jedynej podstawy oceny pracy studenta.**
