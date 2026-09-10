# Dane przestrzenne i źródła danych

## Zakres obecnej wersji

CLI przyjmuje dwa pliki GeoJSON:

1. granicę analizowanego obszaru przez `--site`;
2. warstwy ograniczeń przez `--constraints`.

Program nie pobiera danych z internetu i nie dostarcza urzędowych warstw w
repozytorium. Użytkownik odpowiada za wybór źródła, aktualność i kompletność
danych.

## GeoJSON granicy obszaru

Plik granicy musi być `FeatureCollection` zawierającym dokładnie jeden obiekt
z geometrią. Musi również deklarować CRS z identyfikatorem EPSG, np.:

```json
{
  "type": "FeatureCollection",
  "crs": {"type": "name", "properties": {"name": "EPSG:2180"}},
  "features": [
    {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]]]
      }
    }
  ]
}
```

Adapter odrzuca pustą, niepoprawną lub wieloobiektową warstwę oraz CRS bez
rozpoznawalnego kodu EPSG. Dla bieżących obliczeń powierzchni i buforów należy
stosować CRS o jednostkach metrycznych.

## GeoJSON warstw ograniczeń

Każdy obiekt musi mieć właściwości:

| Właściwość | Znaczenie |
| --- | --- |
| `layer` | nazwa warstwy wskazywana przez `source_layer` w regule YAML |
| `source` | źródło lub identyfikator zbioru danych |
| `version` | wersja, data lub inny stabilny identyfikator danych |

Obiekty o tej samej wartości `layer` są łączone w jedną geometrię. CRS warstw
ograniczeń musi być identyczny z CRS granicy obszaru.

## Pochodzenie i wersjonowanie

Wynik zapisuje wersje warstw i reguł w `metadata.json`, a raport tekstowy
przedstawia je w sekcji „ŹRÓDŁA I WERSJE DANYCH”. Nazwa źródła i wersja nie
zastępują oceny jakości danych: przed użyciem wyniku trzeba sprawdzić datę
pozyskania, zakres, dokładność, kompletność i zgodność CRS.

Planowane źródła danych w kolejnych etapach obejmują dane wiatrowe, dane
nasłonecznienia oraz dalsze źródła techniczne i środowiskowe. Nie są jeszcze
obsługiwane przez adaptery.
