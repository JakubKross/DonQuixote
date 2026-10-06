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
- ✅ Krok 2 — PostGIS i adaptery repozytoriów (`adapters/postgres/`, extra
  `postgres`, migracja Alembic), włączane zmienną `DATABASE_URL` —
  repozytoria w pamięci pozostają domyślne, gdy zmienna nie jest ustawiona;
- ✅ Krok 3 — tabela `jobs`, worker (`renewable_planner.worker`) i
  przełączenie `POST /v1/screenings` na `202`/polling, włączane tą samą
  zmienną `DATABASE_URL` co Krok 2 — bez niej API pozostaje w pełni
  synchroniczne (Krok 1);
- ✅ Krok 4 — frontend React + MapLibre z realną mapą (`frontend/`):
  „Lista analiz”, „Nowy screening”, „Szczegóły analizy” (status z
  pollingiem, mapa) i „Wyniki technologii” (wiatr, PV, hybryda, magazyn —
  formularze i wykresy profili godzinowych);
- ✅ Krok 5 — `docker-compose` (`docker-compose.yml`, `Dockerfile`,
  `frontend/Dockerfile`) uruchamia API + PostGIS + worker + frontend
  jednym poleceniem (`docker compose up --build`) — działa już dziś mimo
  częściowego Kroku 4, bo odpala to, co istnieje.

## Poza obecnym planem etapów

Nieprzypisane jeszcze do konkretnego etapu, wymienione w
[REQUIREMENTS.md](REQUIREMENTS.md#poza-zakresem-obecnej-wersji):

- automatyczne pobieranie urzędowych danych przestrzennych;
- porównywanie scenariuszy hybrydowych obok siebie;
- końcowa kwalifikacja prawna, środowiskowa, planistyczna lub przyłączeniowa.
