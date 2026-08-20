# DonQuixote

DonQuixote jest narzędziem do wstępnego planowania instalacji OZE w Polsce.
Aktualna wersja wykonuje przestrzenny screening obszaru na podstawie granicy
terenu, warstw ograniczeń i wersjonowanych reguł zapisanych w YAML. Pierwsza
wersja koncentruje się na przygotowaniu fundamentu pod analizę lądowych farm
wiatrowych; nie oblicza jeszcze produkcji energii ani rozmieszczenia turbin.

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

## Testy i kontrola jakości

```bash
pytest
ruff format .
ruff check .
mypy src
```

Testy obejmują modele domenowe, walidację CRS i geometrii, silnik reguł,
przypadek użycia screeningu, adaptery plikowe oraz ścieżkę CLI z raportem.

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

## Generowane wyniki

W katalogu wskazanym przez `--output` powstają:

- `metadata.json` — identyfikator i status analizy, podsumowanie powierzchni,
  findingi oraz wersje reguł i warstw;
- `available_area.geojson` — obszar pozostały po zastosowaniu wykluczeń;
- `excluded_areas.geojson` — geometria zsumowanych wykluczeń;
- `report.txt` — raport tekstowy z regułami, ostrzeżeniami, źródłami,
  powierzchniami i zastrzeżeniami dotyczącymi interpretacji wyniku.

Raport jest generowany przez port, dlatego w przyszłości można dodać adapter
HTML lub PDF bez zmiany warstwy aplikacyjnej.

## Dokumentacja

- [Dane przestrzenne i źródła](docs/DATA_SOURCES.md)
- [Reguły prawne i ograniczenia](docs/LEGAL_RULES.md)
- [Format konfiguracji reguł YAML](docs/RULES_FORMAT.md)
- [Architektura](docs/ARCHITECTURE.md)
- [Plan rozwoju](docs/ROADMAP.md)

## Obecne ograniczenia

- brak katalogu turbin, danych wiatrowych i modelu produkcji;
- brak rozmieszczania turbin, minimalnych odległości technologicznych i modelu wake;
- brak integracji z PyWake, pvlib, bazą danych, PostGIS i zewnętrznymi API;
- brak interfejsu mapowego — dostępny jest tylko CLI;
- obsługiwane są pliki GeoJSON, bez automatycznego pobierania danych;
- wynik screeningu nie jest opinią prawną ani decyzją administracyjną;
- konfiguracja CLI wymaga zgodnego CRS między granicą i warstwami ograniczeń.

## Następny etap

Następnym etapem jest moduł wiatrowy: katalog turbin, źródło danych wiatrowych,
uproszczony godzinowy profil produkcji, generowanie rozmieszczenia turbin i
minimalne odstępy. Dopiero po nim planowany jest adapter modelu wake z PyWake.
