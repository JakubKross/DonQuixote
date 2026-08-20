# Plan rozwoju

## Etap 0 — fundament — wykonany

- konfiguracja projektu Python;
- modele domenowe i walidacja podstawowych danych;
- porty repozytoriów, dostawców danych, operacji GIS i raportowania;
- testy jednostkowe oraz test ścieżki CLI;
- CLI i rejestrowanie `AnalysisRun`.

## Etap 1 — analiza przestrzenna — wykonany w wersji pierwszej

- import granicy obszaru z GeoJSON;
- walidacja geometrii i CRS;
- import warstw ograniczeń z GeoJSON;
- reguły YAML z wersją, źródłem i datami obowiązywania;
- bufory, przecięcia, unie i różnice;
- wyznaczanie dostępnego obszaru;
- `metadata.json`, warstwy GeoJSON i tekstowy raport wynikowy.

## Etap 2 — moduł wiatrowy — pierwszy zakres rozpoczęty

- podstawowy katalog turbin z odczytem YAML/JSON — wykonany;
- dane wiatrowe;
- uproszczony godzinowy profil produkcji;
- generowanie rozmieszczenia;
- minimalne odstępy między turbinami.

## Etap 3 — model wake

- adapter PyWake;
- AEP;
- godzinowy profil po uwzględnieniu wake;
- raportowanie strat wake.

## Etap 4 — pierwszy interfejs

- prototyp Streamlit;
- mapa;
- formularz projektu;
- wyświetlanie wyników.

## Etap 5 — fotowoltaika

- dane nasłonecznienia;
- adapter pvlib;
- rozmieszczenie PV;
- godzinowa produkcja.

## Etap 6 — hybryda

- agregacja wiatr + PV;
- limit przyłączenia;
- curtailment;
- wykorzystanie przyłącza.

## Etap 7 — magazyn energii

- model baterii;
- stan naładowania;
- ładowanie nadwyżką;
- ograniczenie strat.

## Etap 8 — wersja webowa

- FastAPI;
- PostGIS;
- procesy robocze;
- React i MapLibre.
