# Reguły prawne i ograniczenia

## Zasada ogólna

DonQuixote wykonuje screening wspierający dalsze decyzje lokalizacyjne. Nie
wydaje wiążącej opinii prawnej, decyzji administracyjnej ani gwarancji, że
inwestycja może zostać zrealizowana.

## Reguły jako dane

Reguły nie są zapisane na stałe w algorytmach. Są dostarczane w wersjonowanym
pliku YAML opisanym w [RULES_FORMAT.md](RULES_FORMAT.md). Każda reguła zawiera
między innymi:

- stabilny identyfikator;
- poziom skutku: `exclusion`, `conditional`, `warning` lub `information`;
- technologie, których dotyczy;
- warstwę źródłową;
- operację `intersects` albo `buffer` i odległość w metrach;
- źródło/podstawę (`legal_basis`);
- `valid_from` oraz opcjonalne `valid_to`.

Reguła jest używana tylko wtedy, gdy dotyczy analizowanej technologii i jest
aktywna w dniu wskazanym przez `--analysis-date`. Walidator odrzuca niepełne
lub niespójne konfiguracje.

## Interpretacja poziomów

- `exclusion` — geometria wpływająca na obszar wykluczany z wyniku;
- `conditional` — ograniczenie wymagające dodatkowych warunków lub oceny;
- `warning` — sygnał ostrzegawczy, który nie jest automatycznym zakazem;
- `information` — informacja kontekstowa.

Tylko aktywne reguły poziomu `exclusion`, które faktycznie oddziałują na
obszar, zmniejszają powierzchnię dostępną. Reguły warunkowe i ostrzegawcze są
raportowane jako wymagające weryfikacji.

## Wymagana weryfikacja

Przed wykorzystaniem wyniku należy sprawdzić co najmniej:

- aktualność podstaw prawnych i okres obowiązywania reguł;
- kompletność i aktualność warstw przestrzennych;
- poprawność CRS, geometrii i jednostek;
- szczegółowe przepisy, decyzje i uzgodnienia właściwe dla lokalizacji;
- wymagania środowiskowe, planistyczne, techniczne i przyłączeniowe.

Raport oraz wynik JSON zawierają źródła i wersje danych, ale nie potwierdzają
ich aktualności. Odpowiedzialność za ocenę prawną i końcową decyzję pozostaje
po stronie użytkownika oraz właściwych ekspertów.

Przykładowe reguły w `config/sample_rules.yaml` są fikcyjne i służą wyłącznie
do demonstracji działania programu; nie należy traktować ich jako aktualnych
wymagań prawnych.
