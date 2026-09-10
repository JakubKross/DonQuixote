# DonQuixote

DonQuixote jest narzędziem do wstępnego planowania instalacji OZE w Polsce.
Aktualna wersja wykonuje przestrzenny screening obszaru na podstawie granicy
terenu, warstw ograniczeń i wersjonowanych reguł zapisanych w YAML, a na
dostępnym obszarze potrafi dodatkowo:

- rozmieścić turbiny wiatrowe i zasymulować ich godzinową produkcję energii
  (wbudowanym symulatorem bez strat wake albo opcjonalnym adapterem PyWake);
- dobrać wielkość instalacji PV i zasymulować jej produkcję DC/AC
  (wbudowanym symulatorem albo opcjonalnym modelem inwertera z pvlib);
- zagregować produkcję wiatru i PV oraz ograniczyć ją (curtailment) do
  zadanego limitu mocy przyłącza;
- naładować/rozładować magazyn energii (baterię) względem tego limitu.

Wszystkie kroki poza podstawowym screeningiem są opcjonalne i sterowane
parametrami CLI — bez katalogu turbin/PV/baterii program ogranicza się do
samego screeningu przestrzennego. Poza CLI dostępne jest też (opcjonalnie)
proste API webowe (FastAPI) i formularz Streamlit, patrz
[Architektura wersji webowej](docs/WEB_ARCHITECTURE.md).

Wynik jest materiałem pomocniczym do dalszej analizy. Nie jest wiążącą opinią
prawną, nie gwarantuje możliwości realizacji inwestycji i wymaga sprawdzenia
aktualności danych oraz oceny eksperta.

## Instalacja

Projekt wymaga Pythona 3.11 lub nowszego. Instalacja zależności produkcyjnych
i narzędzi developerskich:

```bash
python -m pip install -e ".[dev]"
```

Główne zależności to GeoPandas, PyProj, Shapely i PyYAML. Instalacja w
środowisku wirtualnym jest zalecana.

Opcjonalne adaptery i interfejsy doinstalowuje się przez odpowiedni extra:

```bash
python -m pip install -e ".[pywake]"     # model wake dla wiatru (PyWake)
python -m pip install -e ".[pvlib]"      # model inwertera PVWatts dla PV (pvlib)
python -m pip install -e ".[web]"        # API webowe (FastAPI, uvicorn)
python -m pip install -e ".[streamlit]"  # formularz webowy (Streamlit)
```

Bez tych extrasów program działa w pełni (screening, produkcja wiatru/PV,
agregacja hybrydowa, magazyn, CLI) — brakujące zależności są wymagane
wyłącznie przez konkretny opcjonalny adapter lub interfejs.

## Testy i kontrola jakości

```bash
pytest
ruff format .
ruff check .
mypy src
```

Testy obejmują modele domenowe, walidację CRS i geometrii, silnik reguł,
przypadek użycia screeningu, adaptery plikowe, symulacje wiatru/PV,
agregację hybrydową, magazyn energii, composition root, API i formularz
Streamlit, oraz pełną ścieżkę CLI z raportem. Testy integracyjne PyWake,
pvlib i FastAPI (oznaczone markerami `pywake`/`pvlib`/`web`) są pomijane,
gdy odpowiedni extra nie jest zainstalowany.

## Uruchamianie przez CLI

Wersję programu można sprawdzić poleceniem:

```bash
donquixote --version
```

Przykładowa analiza:

```bash
donquixote screen-site \
  --site tests/fixtures/cli_site.geojson \
  --constraints tests/fixtures/cli_constraints.geojson \
  --rules tests/fixtures/cli_rules.yaml \
  --technology wind \
  --country PL \
  --analysis-date 2026-08-17 \
  --output output/screening
```

`--site`, `--constraints`, `--rules` i `--output` są wymagane. Data analizy
steruje aktywnością reguł; domyślnie jest to bieżąca data. W tej wersji plik
graniczny i warstwy ograniczeń muszą używać tego samego CRS z identyfikatorem
EPSG i jednostkami metrycznymi do obliczeń powierzchni oraz buforów.

Produkcja wiatru/PV, agregacja hybrydowa i magazyn są opcjonalne i włączane
odpowiednimi flagami (`--turbine-catalog`/`--wind-resource`,
`--solar-catalog`/`--solar-resource`, `--grid-connection-limit-mw`,
`--battery-catalog`); pełną listę pokazuje `donquixote screen-site --help`.

## Generowane wyniki

W katalogu wskazanym przez `--output` powstają:

- `metadata.json` — identyfikator i status analizy, podsumowanie powierzchni,
  findingi oraz wersje reguł i warstw;
- `available_area.geojson` — obszar pozostały po zastosowaniu wykluczeń;
- `excluded_areas.geojson` — geometria zsumowanych wykluczeń;
- `report.txt` — raport tekstowy z regułami, ostrzeżeniami, źródłami,
  powierzchniami, produkcją wiatru/PV, agregacją hybrydową, magazynem
  (dla uruchomionych kroków) i zastrzeżeniami dotyczącymi interpretacji wyniku;
- `turbine_positions.geojson` — wygenerowane pozycje turbin (tylko gdy podano
  `--turbine-catalog` i pozostał dostępny obszar).

Raport jest generowany przez port, dlatego w przyszłości można dodać adapter
HTML lub PDF bez zmiany warstwy aplikacyjnej.

## Dokumentacja

- [Wymagania projektu](docs/REQUIREMENTS.md)
- [Dane przestrzenne i źródła](docs/DATA_SOURCES.md)
- [Reguły prawne i ograniczenia](docs/LEGAL_RULES.md)
- [Format konfiguracji reguł YAML](docs/RULES_FORMAT.md)
- [Architektura](docs/ARCHITECTURE.md)
- [Architektura wersji webowej](docs/WEB_ARCHITECTURE.md)
- [Plan rozwoju](docs/ROADMAP.md)

## Obecne ograniczenia

- katalog turbin i katalog PV/baterii zawierają wyłącznie dane dostarczone
  w konfiguracji — brak urzędowego katalogu producentów;
- symulacje wiatru/PV zakładają jeden, stały szereg czasowy zasobu dla
  całego obszaru (brak przestrzennego zróżnicowania zasobu w obrębie farmy);
- adaptery PyWake i pvlib są opcjonalne — bez nich program używa wbudowanych,
  uproszczonych symulatorów (bez modelu wake / bez modelu inwertera PVWatts);
- API webowe i repozytoria w pamięci to jawny placeholder (Step 1, patrz
  [docs/WEB_ARCHITECTURE.md](docs/WEB_ARCHITECTURE.md)) — stan nie przetrwa
  restartu procesu i nie jest współdzielony między procesami roboczymi;
- brak interfejsu mapowego (React/MapLibre) — dostępne są CLI, proste API
  i formularz Streamlit;
- obsługiwane są pliki GeoJSON, bez automatycznego pobierania danych;
- wynik screeningu nie jest opinią prawną ani decyzją administracyjną;
- konfiguracja CLI wymaga zgodnego CRS między granicą i warstwami ograniczeń.

## Następny etap

Plan dalszego rozwoju (PostGIS zamiast repozytoriów w pamięci, interfejs
mapowy React/MapLibre i kolejne etapy) opisuje
[docs/ROADMAP.md](docs/ROADMAP.md).
