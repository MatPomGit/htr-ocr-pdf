# Rozpoznawanie pisma ręcznego (HTR/OCR)

Aplikacja renderuje odpowiednie strony obu dokumentów przy takich samych parametrach, dzieli je na wspólne poziome pasy i wysyła każdy pas do lokalnego modelu w Ollama. Domyślny model to `qwen3-vl:4b`.

## Tryby rozpoznawania

- `handwriting`: model jest instruowany, aby przepisał **wyłącznie** treść odręczną, bez tekstu drukowanego.
- `all`: model rozpoznaje także treść drukowaną. Przy eksportowaniu warstwy tekstowej może to powodować duplikację już istniejącego tekstu PDF.

Model powinien zachować polskie znaki i oryginalne błędy pisowni. Nieczytelny fragment powinien oznaczyć `[nieczytelne]`, jednak wynik może zawierać pominięcia, halucynacje lub błędne rozpoznania.

## Parametry

- `--segments 1..6`: liczba pasów poziomych; granice dobierane są z obszarów o małej gęstości ciemnych pikseli.
- `--pages 1-3,5`: ograniczenie analizy do wybranych stron.
- `--max-side 2800`: maksymalny wymiar renderu w pikselach (obsługiwany zakres 1200–6000).
- `--model qwen3-vl:4b`: nazwa pobranego lokalnie modelu.
- `--no-searchable-pdf`: wyłączenie eksportu przeszukiwalnych PDF-ów.

Wywołania używają temperatury 0 i ziarna 42, ale wynik może nadal różnić się między uruchomieniami. W raportach przechowywany jest digest modelu (jeżeli dostępny), ustawienia oraz sumy SHA-256 plików.

## Prywatność i wznawianie

Program odrzuca zdalne adresy serwera Ollama i używa lokalnego HTTP. Żądania zawierające obrazy nie są wysyłane do usług chmurowych. Dokumenty, transkrypcje i raport pozostają na komputerze użytkownika.

Po ukończeniu strony stan zapisywany jest w `checkpoint.json`; wznowienie jest możliwe, jeśli pliki, model i parametry przetwarzania nie uległy zmianie. Zatrzymanie zamyka aktywne połączenie HTTP i odrzuca niekompletną odpowiedź.

Zobacz [eksport wyników](results.md).


## Anulowanie żądania HTR

Klient łączy się z lokalnym `/api/chat` przy użyciu `stream: true`. Fragmenty JSON Lines są łączone w jedną transkrypcję, ale zostają zaakceptowane tylko po odebraniu komunikatu końcowego. Wciśnięcie **Zatrzymaj** ustawia flagę w `CancelToken` oraz zamyka aktywne gniazdo TCP, co przerywa blokujący odczyt. Nie dotyczy to innych żądań Ollama. Przerwana strona nie jest zapisywana jako ukończona w checkpoint.
