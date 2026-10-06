# DonQuixote — frontend

React + TypeScript + Vite, per `docs/WEB_ARCHITECTURE.md` (sekcja 5).
Obsługuje dziś dwa widoki wspierane przez API: nowy screening i jego
szczegóły (status z pollingiem, podsumowanie powierzchni, findingi, mapa
MapLibre). Historia analiz i wyniki per-technologia nie są jeszcze
zbudowane — backend nie udostępnia dla nich endpointów (patrz
`docs/WEB_ARCHITECTURE.md`).

## Uruchomienie

Backend musi działać równolegle (domyślnie tryb pamięciowy, bez
`DATABASE_URL`, w pełni synchroniczny):

```bash
# w katalogu głównym repo
uvicorn renewable_planner.api.app:app --reload
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env   # opcjonalnie, jeśli API nie jest na localhost:8000
npm run dev
```

Otwórz adres wypisany przez Vite (domyślnie `http://localhost:5173`).

## Regeneracja typów API

`src/api/schema.d.ts` jest generowany z OpenAPI schema FastAPI i commitowany
— po każdej zmianie kontraktu API w `src/renewable_planner/api/` uruchom:

```bash
# w katalogu głównym repo, w aktywnym środowisku z zainstalowanym [web]
python -c "import json; from renewable_planner.api.app import app; print(json.dumps(app.openapi()))" > frontend/openapi.json
cd frontend
npm run generate:api-types
```

## Build produkcyjny

```bash
npm run build   # tsc -b && vite build, wynik w dist/
```

Zobacz też `docker-compose.yml`/`frontend/Dockerfile` w katalogu głównym
repo — `docker compose up --build` buduje i serwuje ten build produkcyjny
przez nginx razem z API/Postgresem/workerem, jednym poleceniem.

## Worker MapLibre — `setWorkerUrl`, nie automatyczne wykrywanie

`maplibre-gl` normalnie sam odnajduje swój plik workera kafelkowego przez
`new Worker(new URL(...))` względem `import.meta.url`, ale to nie
przeżywa produkcyjnego builda (Rollup nie wykrywa tego wzorca głęboko
wewnątrz `node_modules`) — mapa renderowała się pusto z błędem „Worker
failed to load”. Zamiast tego: skrypt `postinstall` (w `package.json`)
kopiuje `maplibre-gl-worker.mjs` razem z `maplibre-gl-shared.mjs` (worker
importuje go względną ścieżką, musi leżeć obok) z `node_modules` do
`public/maplibre-gl/` (katalog generowany, w `.gitignore`), a
`src/components/ScreeningMap.tsx` wywołuje `setWorkerUrl(...)` wskazując na
tę kopię, zanim powstanie jakakolwiek `Map`. Przy podnoszeniu wersji
`maplibre-gl` wystarczy `npm install` — `postinstall` uruchamia się
automatycznie.
