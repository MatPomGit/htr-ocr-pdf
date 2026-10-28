# Metryki tekstowe i obrazowe

## Rozbieżność transkrypcji

Dla znormalizowanych tekstów `A` i `B`:

`char_disagreement = Levenshtein(A,B) / max(len(A),len(B))`

`word_disagreement = Levenshtein(words(A),words(B)) / max(word_count(A),word_count(B))`

Dwa puste teksty dają wynik 0. To miary rozbieżności, nie dokładności transkrypcji.

## CER i WER względem referencji

Dla tekstu referencyjnego `R` i wyniku `T`:

`CER = Levenshtein(R,T) / len(R)`

`WER = Levenshtein(words(R),words(T)) / word_count(R)`

Pusta referencja z niepustą predykcją daje wartość `null`. Referencja może mieć format:

```text
=== PAGE 1 ===
tekst referencyjny pierwszej strony
=== PAGE 2 ===
tekst referencyjny drugiej strony
```

Parametr CLI: `--reference reference.txt`.

## Metryki obrazu

RMSE oblicza się na wyrenderowanych obrazach RGB, w zakresie kanałów 0–255; w JSON zapisywana jest wartość znormalizowana do 0–1. PSNR: `20 × log10(255 / RMSE_raw)`, w decybelach. Dla identycznych obrazów PSNR jest nieskończony i zapisywane jest `null`. Zgodność obrazów nie dowodzi zgodności transkrypcji.
