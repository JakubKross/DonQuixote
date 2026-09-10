# Format konfiguracji reguł przestrzennych

Konfiguracja reguł jest plikiem YAML zawierającym listę pod kluczem `rules`.
Przykład znajduje się w [`config/sample_rules.yaml`](../config/sample_rules.yaml).

Każdy element listy ma następujące pola:

| Pole | Typ / wartości | Znaczenie |
| --- | --- | --- |
| `id` | UUID | Stabilny identyfikator reguły. |
| `name` | niepusty tekst | Nazwa reguły. |
| `severity` | `exclusion`, `conditional`, `warning`, `information` | Poziom skutku reguły. |
| `applies_to` | niepusta lista tekstów | Technologie, których dotyczy reguła. |
| `source_layer` | niepusty tekst | Nazwa wymaganej warstwy z danych ograniczeń. |
| `operation` | `intersects` albo `buffer` | Operacja wyznaczająca obszar oddziaływania. |
| `distance_m` | nieujemna, skończona liczba | Odległość bufora w metrach. Dla `intersects` zalecane jest `0`. |
| `legal_basis` | niepusty tekst | Źródło lub podstawa zastosowania reguły. |
| `valid_from` | data `YYYY-MM-DD` | Pierwszy dzień obowiązywania. |
| `valid_to` | data `YYYY-MM-DD` albo brak | Ostatni dzień obowiązywania. Nie może poprzedzać `valid_from`. |

Walidator sprawdza typy i wartości przed utworzeniem modelu domenowego. Błąd
wskazuje dokładne pole, np. `rules[0].distance_m`. Nieznane poziomy, brak `id`,
pusta lista technologii, brak `source_layer`, ujemne odległości i niepoprawne
daty są odrzucane.

Plik jest wczytywany przez `yaml.safe_load`; zawartość YAML nie jest wykonywana.
`source_layer` musi odpowiadać warstwie dostępnej w pliku `--constraints`.
