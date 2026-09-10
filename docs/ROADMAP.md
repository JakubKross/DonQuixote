# Plan rozwoju

## Etap 0 — fundament — wykonany

- konfiguracja projektu Python;
- modele domenowe i walidacja podstawowych danych;
- porty repozytoriów, dostawców danych, operacji GIS i raportowania;
- testy jednostkowe oraz test ścieżki CLI;
- CLI i rejestrowanie `AnalysisRun`.

## Etap 1 — analiza przestrzenna — wykonany

- import granicy obszaru z GeoJSON;
- walidacja geometrii i CRS;
- import warstw ograniczeń z GeoJSON;
- reguły YAML z wersją, źródłem i datami obowiązywania;
- bufory, przecięcia, unie i różnice;
- wyznaczanie dostępnego obszaru;
- `metadata.json`, warstwy GeoJSON i tekstowy raport wynikowy.

## Etap 2 — moduł wiatrowy — wykonany

- katalog turbin z odczytem YAML/JSON;
- dane wiatrowe (godzinowy szereg czasowy prędkości i kierunku wiatru);
- uproszczony godzinowy profil produkcji (bez modelu wake);
- generowanie rozmieszczenia turbin na dostępnym obszarze z minimalnymi
  odstępami.

## Etap 3 — model wake — wykonany

- adapter PyWake (opcjonalny, extra `pywake`);
- AEP z uwzględnieniem i bez uwzględnienia wake;
- godzinowy profil po uwzględnieniu wake per turbina i dla całej farmy;
- raportowanie strat wake w `report.txt`.

## Etap 4 — pierwszy interfejs — częściowo wykonany

- prototyp Streamlit (`streamlit_app.py`) — wykonany, wywołuje te same
  przypadki użycia co CLI przez `composition`;
- formularz projektu i wyświetlanie wyników (metadane, findingi, produkcja) —
  wykonane;
- mapa — częściowo: obecnie schematyczny podgląd SVG bez georeferencji
  (`render_schematic_map_svg`), nie prawdziwa mapa z podkładem. Realna mapa
  (MapLibre) jest zaplanowana dopiero we froncie webowym, patrz Etap 8 /
  Krok 4 w [WEB_ARCHITECTURE.md](WEB_ARCHITECTURE.md).

## Etap 5 — fotowoltaika — wykonany

- dane nasłonecznienia (godzinowy szereg czasowy napromieniowania i
  temperatury otoczenia);
- dobór wielkości instalacji PV na dostępnym obszarze (ground coverage
  ratio);
- adapter pvlib (opcjonalny, extra `pvlib`, model inwertera PVWatts);
- godzinowa produkcja DC/AC wbudowanym symulatorem albo pvlib.

## Etap 6 — hybryda — wykonany

- agregacja profili wiatr + PV w jeden profil energii;
- model limitu przyłączenia (`GridConnectionLimit`);
- curtailment przy ograniczonym przyłączu;
- raportowanie wykorzystania przyłącza.

## Etap 7 — magazyn energii — wykonany

- model baterii i katalog baterii (YAML/JSON);
- dyspozycja (dispatch) względem zagregowanego profilu i limitu przyłącza;
- ładowanie nadwyżką, rozładowanie zgodnie z ograniczeniami mocy i
  pojemności;
- uwzględnienie strat magazynu (round-trip) i raportowanie końcowego stanu
  naładowania.

## Etap 8 — wersja webowa — rozpoczęty

Szczegółowy plan i status poszczególnych kroków prowadzi
[WEB_ARCHITECTURE.md](WEB_ARCHITECTURE.md#9-status-implementacji):

- ✅ Krok 1 — FastAPI na adapterach plikowych i repozytoriach w pamięci,
  działanie synchroniczne (`src/renewable_planner/api/`, extra `web`);
- ⬜ Krok 2 — PostGIS i adaptery repozytoriów zastępujące repozytoria w
  pamięci (obecnie stan nie przetrwa restartu procesu i nie jest
  współdzielony między procesami roboczymi) — **następny priorytet**;
- ⬜ Krok 3 — tabela `jobs`, worker i przełączenie API na `202`/polling;
- ⬜ Krok 4 — frontend React + MapLibre z realną mapą;
- ⬜ Krok 5 — `docker-compose` do uruchomienia całości.

## Poza obecnym planem etapów

Nieprzypisane jeszcze do konkretnego etapu, wymienione w
[REQUIREMENTS.md](REQUIREMENTS.md#poza-zakresem-obecnej-wersji):

- automatyczne pobieranie urzędowych danych przestrzennych;
- porównywanie scenariuszy hybrydowych obok siebie;
- końcowa kwalifikacja prawna, środowiskowa, planistyczna lub przyłączeniowa.
