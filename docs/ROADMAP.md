# Plan rozwoju

## Etap 0 — fundament

- konfiguracja projektu Python,
- modele domenowe,
- porty repozytoriów,
- system testów,
- CLI,
- rejestrowanie AnalysisRun.

## Etap 1 — analiza przestrzenna

- import granicy obszaru,
- walidacja CRS,
- import warstw ograniczeń,
- bufory,
- przecięcia,
- wyznaczanie dostępnego obszaru,
- raport wynikowy.

## Etap 2 — moduł wiatrowy

- katalog turbin,
- dane wiatrowe,
- prosty profil produkcji,
- generowanie rozmieszczenia,
- minimalne odstępy.

## Etap 3 — model wake

- adapter PyWake,
- AEP,
- godzinowy profil,
- straty wake.

## Etap 4 — pierwszy interfejs

- prototyp Streamlit,
- mapa,
- formularz projektu,
- wyświetlanie wyników.

## Etap 5 — fotowoltaika

- dane nasłonecznienia,
- adapter pvlib,
- rozmieszczenie PV,
- godzinowa produkcja.

## Etap 6 — hybryda

- agregacja wiatr + PV,
- limit przyłączenia,
- curtailment,
- wykorzystanie przyłącza.

## Etap 7 — magazyn energii

- model baterii,
- stan naładowania,
- ładowanie nadwyżką,
- ograniczenie strat.

## Etap 8 — wersja webowa

- FastAPI,
- PostGIS,
- procesy robocze,
- React i MapLibre.