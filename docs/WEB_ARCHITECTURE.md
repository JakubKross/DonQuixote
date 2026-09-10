# Architektura wersji webowej (Etap 8)

Ten dokument projektuje Etap 8 z ROADMAP.md: **FastAPI, PostGIS, procesy robocze,
React i MapLibre**. Etap 8 zaczyna się dopiero po zakończeniu Etapów 0–7 (screening,
wiatr, PV, hybryda, magazyn) — co już nastąpiło. Celem jest udostępnienie istniejących
przypadków użycia przez API sieciowe i przeglądarkę, **bez zmiany** logiki domenowej
i aplikacyjnej. Zgodnie z AGENTS.md logika domenowa nie może importować FastAPI,
bazy danych ani żadnego kodu tego etapu — cały nowy kod to adaptery i interfejsy.

To dokument projektowy, nie kod. Implementacja przebiega w małych, weryfikowalnych
krokach opisanych w sekcji 8 — każdy krok osobno, z testami, zanim zacznie się
następny.

## 1. Co się zmienia, a co nie

Nie zmienia się: `domain/`, `application/`, `ports/`. Cały Etap 8 to nowe adaptery
(baza danych, worker) i nowy interfejs (`api/` — FastAPI) plus osobny frontend.
Adaptery plikowe (`adapters/geospatial/file_screening.py` itd.) i CLI **zostają** —
są używane przez testy i przez tryb lokalny/offline; web nie ich zastępuje, tylko
dodaje alternatywną ścieżkę.

```
Frontend (React + MapLibre)
        │  HTTP/JSON
        ▼
FastAPI (interfejs — jak CLI/Streamlit, wywołuje tylko use case'y)
        │
        ▼
Application (ScreenSite, GenerateTurbineLayout, SizeSolarArray,
              AggregateHybridProduction, DispatchBattery, GenerateAnalysisReport)
        │
        ▼
Ports (repozytoria, dostawcy, symulatory — te same protokoły co dziś)
        │
        ├── Adaptery plikowe (istniejące, bez zmian) — CLI, testy, tryb offline
        └── Adaptery PostGIS (nowe) — web, trwałość, historia analiz
```

## 2. FastAPI — kontrakt API

### 2.1 Model wykonania: asynchroniczny od początku

`AnalysisRun` ma już w domenie stan `pending → running → completed/failed`
(zaprojektowany w Etapie 0, nieużywany jak dotąd w pełni — CLI wykonuje wszystko
synchronicznie w jednym procesie). Web wykorzystuje ten sam model, ale naprawdę
asynchronicznie: `POST` tworzy rekord i zwraca `202 Accepted` z identyfikatorem,
worker (sekcja 4) wykonuje pracę w tle, klient odpytuje `GET` o status. To jest
właśnie powód, dla którego `AnalysisRun` miał te stany od początku — Etap 8 je
w końcu wykorzystuje.

Synchroniczne API (jak w CLI) nie wystarcza w wersji webowej: screening z
symulacją wiatru/PV/magazynu może trwać dłużej niż rozsądny timeout HTTP,
a wielu użytkowników jednocześnie oznacza kolejkowanie.

### 2.2 Zasoby

| Zasób | Operacje | Uwagi |
|---|---|---|
| `POST /v1/projects` | utworzenie projektu | odpowiednik `Project` |
| `POST /v1/projects/{id}/sites` | dodanie granicy terenu | upload GeoJSON (multipart) → ten sam `GeoJsonSiteBoundaryProvider` |
| `POST /v1/screenings` | uruchomienie screeningu | body: `project_id`, `site_id`, `technology`, `country`, `rules_id`/upload, `constraints` upload → tworzy `AnalysisRun(status=pending)`, wpis do tabeli `jobs`, `202` + `Location` |
| `GET /v1/screenings/{id}` | status i wynik | `pending`/`running`/`completed`/`failed`; po `completed` zawiera podsumowanie powierzchni i findingi |
| `GET /v1/screenings/{id}/report` | raport tekstowy | z portu `AnalysisReportGenerator` (ten sam co CLI) |
| `GET /v1/screenings/{id}/layers/{available|excluded}` | GeoJSON wynikowy | do MapLibre |
| `POST /v1/screenings/{id}/turbine-layout` | rozmieszczenie turbin | wymaga `completed` screeningu; analogicznie tworzy job |
| `POST /v1/screenings/{id}/solar-array` | wymiarowanie PV | jak wyżej |
| `POST /v1/screenings/{id}/hybrid` | agregacja + limit przyłącza | wymaga wyniku wiatru i/lub PV |
| `POST /v1/screenings/{id}/battery-dispatch` | dyspozycja magazynu | wymaga wyniku hybrydowego |

Każdy `POST` wywołuje **wyłącznie** istniejący use case przez `composition.py`
(rozszerzony o warianty PostGIS — sekcja 3) — żadnej logiki GIS w warstwie `api/`,
tak jak dziś w `cli.py` i `streamlit_app.py`.

### 2.3 Błędy

Middleware mapuje wyjątki domenowe/aplikacyjne na kody HTTP, analogicznie do
`parser.error(...)` w CLI:

- `*ValidationError`, `ScreenSiteError` i pochodne → `422 Unprocessable Entity` z treścią błędu;
- błędy „nie znaleziono” (`ProjectNotFoundError`, `SiteNotFoundError`) → `404`;
- `NoAvailableAreaError` (wiatr/PV) → `200` z wynikiem informującym o braku obszaru, **nie** błąd — to prawidłowy wynik biznesowy, tak jak w CLI, który też nie traktuje tego jako awarię;
- nieoczekiwane wyjątki → `500`, zalogowane, treść nie ujawnia szczegółów wewnętrznych.

### 2.4 Pliki wejściowe

Upload przez `multipart/form-data`, zapisywany do tymczasowego katalogu i
przekazywany do **tych samych** funkcji plikowych (`load_site`,
`GeoJsonConstraintLayerProvider`, `YamlSpatialRuleProvider`) — identyczny wzorzec
jak w `streamlit_app.py::run_screening`. Żadnego nowego parsera GeoJSON/YAML.

### 2.5 Zależności i uruchomienie

Nowy opcjonalny extra `web` w `pyproject.toml`: `fastapi`, `uvicorn`,
`python-multipart`. Uruchamianie: `uvicorn renewable_planner.api.app:app`.
Dokumentacja API generowana automatycznie przez FastAPI (`/docs`).

## 3. Baza danych i PostGIS

### 3.1 Dlaczego PostGIS, i co dokładnie się zmienia

Obecne repozytoria (`FileProjectRepository`, `MemoryAnalysisRunRepository`,
`JsonResultRepository`) są efemeryczne — żyją tylko w pamięci jednego procesu
CLI. Web wymaga trwałości między requestami i procesem workera, więc potrzebne
są **nowe implementacje istniejących portów** (`ProjectRepository`,
`SiteRepository`, `AnalysisRunRepository`, `SiteScreeningResultRepository`,
`SpatialRuleProvider`, `SpatialDataLayerProvider`) — nic w `ports/` się nie
zmienia, tylko przybywa adapter `adapters/postgres/`.

PostGIS (nie zwykły Postgres) jest potrzebny, bo `Site.boundary` i warstwy
ograniczeń to geometrie — przechowywanie ich jako surowy WKT w kolumnie
tekstowej działałoby, ale traci indeksy przestrzenne (`GiST`) i możliwość
zapytań typu „warstwy przecinające tę granicę” bezpośrednio w bazie, co będzie
potrzebne, gdy warstwy ograniczeń przestaną być plikami dostarczanymi ręcznie
(przyszłe źródła urzędowe — poza zakresem obecnego etapu, ale PostGIS to
przygotowuje).

### 3.2 Schemat (szkic)

```sql
projects            (id uuid pk, name text, description text, created_at timestamptz)
sites               (id uuid pk, project_id uuid fk, name text,
                      boundary geometry(GEOMETRY, ?) srid, boundary_crs text)
spatial_constraints (id uuid pk, name text, category text, geometry geometry,
                      rule_version text, source text, valid_from date, valid_to date,
                      level text, technologies text[], required_layer text,
                      buffer_meters double precision, operation text, legal_basis text)
spatial_data_layers  (id uuid pk, name text, geometry geometry, source text, version text)
analysis_runs        (id uuid pk, project_id uuid, site_id uuid, technology text,
                      country text, parameters jsonb, data_versions jsonb,
                      status text, created_at, started_at, finished_at, error_message text)
constraint_findings  (id uuid pk, analysis_run_id uuid fk, constraint_id uuid,
                      status text, message text, analyzed_at timestamptz,
                      affected_geometry geometry, level text,
                      data_source text, data_version text, requires_expert_review bool)
screening_results    (analysis_run_id uuid pk/fk, excluded_geometry geometry,
                      remaining_geometry geometry, initial_area_m2, excluded_area_m2,
                      available_area_m2)
jobs                 (id uuid pk, job_type text, payload jsonb, status text,
                      analysis_run_id uuid, created_at, locked_at, locked_by text,
                      attempts int, last_error text)
```

Geometrie **nie** przechowują CRS jako część typu kolumny sztywno — SRID
kolumny odpowiada metrycznemu CRS analizy (np. `EPSG:2180` dla Polski), zgodnie
z tym, że dziś `MetricSpatialContext` już wymusza jeden analityczny CRS. Adapter
PostGIS musi wołać ten sam `CoordinateReferenceSystemService` przy zapisie/odczycie,
żeby domena nadal widziała neutralny `SpatialGeometry` (WKT + kod EPSG), nigdy
obiektu specyficznego dla biblioteki.

### 3.3 Adapter

- `adapters/postgres/` — nowy pakiet, analogiczny strukturalnie do
  `adapters/geospatial/`. Każda klasa implementuje jeden port
  (`PostgresProjectRepository`, `PostgresSiteRepository`,
  `PostgresAnalysisRunRepository`, `PostgresScreeningResultRepository`,
  `PostgresSpatialRuleProvider`, `PostgresSpatialDataLayerProvider`).
- Sterownik: `psycopg` (v3) — bez ORM. GeoAlchemy2/SQLAlchemy jest wygodny, ale
  dodaje warstwę mapowania, którą trzeba utrzymywać w synchronizacji z ręcznie
  pisanymi konwersjami domain↔SQL; przy niewielkiej liczbie tabel czysty SQL +
  `psycopg.sql` jest prostszy do audytu i bliższy filozofii projektu („nie
  dodawaj zależności bez uzasadnienia”). Do rewizji, jeśli liczba tabel wzrośnie.
- Migracje: **Alembic** — standard dla projektów bez ORM-owego autogenerowania
  schematu; migracje pisane ręcznie (proste DDL + `CREATE EXTENSION postgis`).
- Konwersja `SpatialGeometry` (WKT) ↔ PostGIS: `ST_GeomFromText(wkt, srid)` /
  `ST_AsText(geom)` po stronie SQL — adapter nigdy nie importuje Shapely dla
  samej serializacji (może użyć go tam, gdzie już dziś się to dzieje, np. przy
  operacjach przestrzennych — bez zmian).

### 3.4 Testowanie bez zgadywania

Testy adaptera Postgres wymagają realnej instancji PostGIS — **testcontainers**
(`testcontainers[postgres]`, opcjonalna zależność deweloperska) uruchamia
efemeryczny kontener Postgres+PostGIS na czas testów, bez potrzeby ręcznej
instalacji bazy w środowisku dev. Testy te oznaczone markerem `postgres` (jak
`pywake`/`pvlib`) i pomijane, gdy Docker nie jest dostępny.

**Otwarte pytanie do Ciebie:** czy masz dostęp do Dockera w środowisku, w
którym te testy będą uruchamiane (lokalnie/CI)? Jeśli nie, alternatywą jest
wskazanie już istniejącej instancji Postgres+PostGIS do testów.

## 4. Procesy robocze

### 4.1 Decyzja: kolejka w tabeli, nie broker

Zamiast Celery/RQ (wymagają Redis/RabbitMQ — kolejnej usługi do wdrożenia i
utrzymania), pierwsza wersja używa **tabeli `jobs` w tej samej bazie Postgres**,
odpytywanej przez prosty worker (`SELECT ... FOR UPDATE SKIP LOCKED`). To
mniejsza powierzchnia infrastruktury (jedna usługa — Postgres — a nie dwie),
wystarczająca przy skali „wstępny screening”, i łatwa do zastąpienia Celery
później, jeśli przepustowość tego wymaga — bez zmiany API czy domeny, bo
worker i tak tylko woła te same use case'y.

### 4.2 Przepływ

1. `POST /v1/screenings` → `AnalysisRunRepository.save()` (status `pending`) +
   wiersz w `jobs` (`status='queued'`, `payload` = zwalidowane wejście).
2. Worker (osobny proces, `python -m renewable_planner.worker`) w pętli:
   pobiera zablokowany wiersz `jobs`, mapuje `payload` na `ScreenSiteCommand`,
   woła `ScreenSite.execute(...)` (bez zmian w use case — `AnalysisRun.start()`/
   `.complete()`/`.fail()` już to obsługują), zapisuje wynik, oznacza `jobs`
   jako `done`/`failed`.
3. `GET /v1/screenings/{id}` czyta `AnalysisRunRepository` — nie zna workera.

### 4.3 Niezawodność

- Ponowne próby: `attempts`/`last_error` w `jobs`, limit prób, potem `AnalysisRun.fail(...)`.
- Worker bezstanowy — restart nie gubi kolejki (leży w bazie).
- Jeden typ joba na razie (screening); rozmieszczenie turbin/PV/hybryda/magazyn
  jako kolejne typy jobów o tym samym mechanizmie, gdy okażą się wolne — na
  początek mogą działać synchronicznie w request/response, bo są rzędy
  wielkości szybsze niż screening z odczytem plików GIS.

## 5. Frontend — React + MapLibre

### 5.1 Stack i miejsce w repo

`frontend/` jako osobny katalog w tym samym repozytorium (monorepo) — ułatwia
trzymanie kontraktu API i UI w jednym PR podczas zmian. **Vite + React +
TypeScript**: najlżejszy z powszechnie przyjętych zestawów, brak potrzeby
frameworka serwerowego (Next.js) dla aplikacji, która tylko woła REST API.

### 5.2 Widoki (mirror Streamlit, plus to, co asynchroniczność umożliwia)

| Widok | Zawartość |
|---|---|
| Nowy screening | upload granicy + ograniczeń, wybór technologii/reguł, submit |
| Lista analiz | historia (dzięki trwałości w Postgres — czego Streamlit/CLI nie miały) |
| Szczegóły analizy | status z odpytywaniem (polling co kilka sekund do `completed`/`failed`), podsumowanie powierzchni, tabela findingów |
| Mapa | MapLibre z warstwami GeoJSON (`available_area`, `excluded_areas`, `turbine_positions`) — realny podkład mapowy (OSM/MapLibre style), w przeciwieństwie do schematycznego SVG w Streamlit, bo tu mamy prawdziwe współrzędne geograficzne do dyspozycji przez API |
| Wyniki technologii | wiatr/PV/hybryda/magazyn — wykresy AEP, strat, curtailmentu |
| Pobranie | raport, GeoJSON, metadata.json |

### 5.3 Komunikacja z API

Klient TypeScript generowany z OpenAPI (`openapi-typescript` + `fetch`) —
kontrakt zawsze zsynchronizowany z FastAPI, bez ręcznie pisanych typów, które
mogą się rozjechać.

### 5.4 Poza zakresem (na razie)

Zaawansowany edytor mapy (rysowanie granicy w przeglądarce), autoryzacja/konta
użytkowników, tryb wielu jednocześnie edytowanych projektów — żadne z tych nie
jest wymagane przez ROADMAP.md dla Etapu 8 i nie powinny wejść „przy okazji”.

## 6. Bezpieczeństwo — świadome ograniczenia tego etapu

Zgodnie z zasadą projektu „nie buduj systemu użytkowników bez wyraźnego
polecenia” (dotąd dotyczyło to Streamlit, teraz web): **brak uwierzytelniania
w pierwszej wersji**. To znacząca różnica względem CLI/Streamlit (uruchamiane
lokalnie przez jedną osobę) — API sieciowe bez autoryzacji nie powinno być
wystawione publicznie. Pierwsza wersja jest przeznaczona do wdrożenia za
zaporą sieciową / w sieci wewnętrznej, z jawną notatką w README, gdy dokumentacja
zostanie zaktualizowana. Podstawowe minimum higieny: limit rozmiaru uploadu,
CORS ograniczony do znanych originów frontendu, brak wykonywania YAML (już
zapewnione przez `yaml.safe_load` w istniejących adapterach).

## 7. Plan wdrożenia — małe kroki

Każdy krok kończy się działającym, przetestowanym stanem, zanim zacznie się
następny — zgodnie z AGENTS.md.

1. **FastAPI, synchronicznie, na adapterach plikowych** — `POST /v1/screenings`
   od razu wykonuje `ScreenSite` (jak CLI) i zwraca `200` z wynikiem; brak bazy,
   brak workera. Cel: kontrakt API i obsługa uploadów, zero nowej infrastruktury.
   Testowalne natychmiast przez `TestClient`.
2. **Model Postgres/PostGIS + adaptery repozytoriów** — migracja z plikowych na
   trwałe, wciąż synchronicznie. Wymaga testcontainers lub wskazanej instancji
   (patrz otwarte pytanie w 3.4).
3. **Tabela `jobs` + worker + przełączenie API na `202`/polling** — dopiero
   teraz API staje się asynchroniczne.
4. **Frontend React + MapLibre** — po ustabilizowaniu kontraktu API.
5. **`docker-compose`** do uruchomienia API + Postgres + worker + frontend
   lokalnie jednym poleceniem.

## 8. Otwarte pytania — rozstrzygnięte

- **Docker**: niedostępny w bieżącym środowisku sesji deweloperskiej, ale można
  go wdrożyć w środowisku, gdzie faktycznie uruchamiane będą testy adaptera
  Postgres (Krok 2). Do tego czasu testy `postgres` pozostają pominięte, tak
  jak `pywake`/`pvlib` są dziś pomijane bez zainstalowanych zależności.
- **Frontend**: **monorepo** (`frontend/` w tym samym repozytorium) — jeden
  kontrakt API i UI zmieniane w tym samym PR, bez podwójnego wersjonowania
  między dwoma repozytoriami.
- **Worker**: potwierdzona **tabela `jobs`** w Postgresie (bez Celery/RQ) —
  jedna usługa infrastruktury zamiast dwóch.
- **Autoryzacja**: brak w pierwszej wersji — zgodnie z sekcją 6, wdrożenie
  wyłącznie za zaporą sieciową/wewnętrznie, do czasu wprowadzenia uwierzytelniania.

## 9. Status implementacji

- ✅ **Krok 1 — FastAPI na adapterach plikowych, synchronicznie.**
  `src/renewable_planner/api/` (`app.py`, `schemas.py`), nowy opcjonalny
  extra `web` w `pyproject.toml`. Endpointy: `POST /v1/screenings`,
  `GET /v1/screenings/{id}`, `GET /v1/screenings/{id}/report`,
  `GET /v1/screenings/{id}/layers/{available|excluded}`. Stan trzymany w
  nowych, współdzielonych w procesie adapterach pamięciowych
  (`adapters/memory_repositories.py`, implementujących te same porty
  `ProjectRepository`/`AnalysisRunRepository`/`SiteScreeningResultRepository`
  co dziś, plus nowe protokoły odczytu `AnalysisRunQuery`/
  `ScreeningResultQuery` w `ports/screening.py`) — zamiast jednorazowych
  instancji CLI/Streamlit. `composition.build_file_screen_site` przyjmuje te
  repozytoria jako opcjonalne argumenty (domyślne zachowanie CLI/Streamlit
  bez zmian). Zweryfikowane testami (`tests/test_api.py`,
  `tests/test_memory_repositories.py`, marker `web`) oraz realnym serwerem
  `uvicorn` (nie tylko `TestClient`).
- ⬜ Krok 2 — PostGIS + adaptery repozytoriów.
- ⬜ Krok 3 — tabela `jobs` + worker + `202`/polling.
- ⬜ Krok 4 — frontend React + MapLibre.
- ⬜ Krok 5 — `docker-compose`.
