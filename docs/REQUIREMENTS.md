# Wymagania projektu

## Cel

DonQuixote jest narzędziem wspomagającym wstępne planowanie instalacji OZE
w Polsce. Pierwsza wersja koncentruje się na lądowych farmach wiatrowych.
Wyniki mają wspierać dalszą analizę lokalizacyjną, ale nie zastępują opinii
prawnej, decyzji administracyjnej ani bankowalnej prognozy produkcji.

## Wymagania funkcjonalne obecnego MVP

### Screening przestrzenny

System musi:

- przyjmować granicę analizowanego obszaru z pliku GeoJSON;
- wymagać dokładnie jednej geometrii granicy oraz deklaracji CRS z kodem EPSG;
- odrzucać puste, niepoprawne i niejednoznaczne dane przestrzenne;
- przyjmować warstwy ograniczeń z pliku GeoJSON;
- wymagać dla każdej warstwy nazwy, źródła i wersji danych;
- wymagać zgodnego, metrycznego CRS dla granicy i warstw ograniczeń;
- wczytywać reguły przestrzenne z wersjonowanego pliku YAML;
- uwzględniać technologię oraz datę analizy przy wyborze aktywnych reguł;
- obsługiwać poziomy skutku: `exclusion`, `conditional`, `warning`
  i `information`;
- obsługiwać operacje przecięcia oraz bufora wyrażonego w metrach;
- wyznaczać geometrie wykluczeń i pozostałego obszaru;
- obliczać początkową, wykluczoną i dostępną powierzchnię;
- zapisywać identyfikator analizy, status, wersje reguł i warstw oraz findingi;
- generować wynikowe warstwy GeoJSON i raport tekstowy ze źródłami danych;
- wskazywać elementy wymagające weryfikacji eksperta.

### Katalog turbin — pierwszy zakres modułu `wind`

System musi:

- przechowywać producenta i nazwę modelu turbiny;
- przechowywać moc znamionową w kW, średnicę wirnika i wysokość piasty w m;
- przechowywać prędkości załączenia, znamionową i wyłączenia w m/s;
- przechowywać uporządkowaną, uproszczoną krzywą mocy w punktach m/s–kW;
- przechowywać źródło i wersję danych;
- walidować jednostki wynikające z nazw pól oraz zakresy i skończoność wartości;
- odczytywać katalog z YAML lub JSON;
- nie wymagać PyWake do utworzenia ani odczytu modelu turbiny.

### Interfejs i uruchamianie

Obecna wersja musi udostępniać przypadek użycia screeningu przez CLI
`screen-site` z wymaganymi argumentami:

- `--site` — granica obszaru;
- `--constraints` — warstwy ograniczeń;
- `--rules` — konfiguracja reguł;
- `--technology` — analizowana technologia;
- `--output` — katalog wynikowy.

Data analizy i kraj powinny być konfigurowalne. Domyślnym krajem jest Polska,
a brak daty oznacza bieżącą datę.

## Wymagania niefunkcjonalne

- Logika domenowa nie może zależeć od GeoPandas, PyProj, PyWake, pvlib,
  FastAPI, Streamlit ani kodu bazy danych.
- Biblioteki zewnętrzne muszą być ukryte za adapterami i portami.
- Interfejs użytkownika może wywoływać wyłącznie przypadki użycia.
- Moduły wind, solar, storage i grid muszą pozostać niezależne.
- Dane przestrzenne muszą mieć jawny CRS, a obliczenia powierzchni i buforów
  muszą używać jednostek metrycznych.
- Reguły prawne muszą być wersjonowanymi danymi lub konfiguracją, a nie
  niezmiennymi wartościami zapisanymi w algorytmie.
- Każdy wynik powinien zawierać źródła danych, ich wersje, datę analizy,
  zastosowane reguły, poziom niepewności lub zastrzeżenia oraz elementy do
  weryfikacji eksperta.
- Nowa logika domenowa musi mieć testy, a kod powinien używać type hints,
  małych funkcji i `pathlib`.

System powinien również:

- działać deterministycznie dla tych samych danych, reguł i parametrów;
- zwracać czytelne błędy dla brakujących, niepoprawnych lub niespójnych danych;
- rejestrować status analizy oraz błąd nieudanego przebiegu;
- umożliwiać wymianę adaptera raportu bez zmiany przypadku użycia screeningu;
- nie wymagać mikroserwisów ani globalnego stanu.

## Poza zakresem obecnej wersji

Poniższe funkcje nie są wymagane do ukończenia obecnego etapu screeningu:

- automatyczne pobieranie urzędowych danych przestrzennych;
- interfejs mapowy, Streamlit, FastAPI, frontend webowy i PostGIS;
- rozmieszczanie turbin;
- dane wiatrowe i godzinowy profil produkcji;
- model wake i integracja z PyWake;
- moduły fotowoltaiki, magazynu energii, sieci i hybrydy;
- końcowa kwalifikacja prawna, środowiskowa, planistyczna lub przyłączeniowa.

## Planowane rozszerzenia

Rozszerzenia muszą pozostać niezależnymi modułami technologicznymi i wymieniać
wyniki przez wspólne modele domenowe. Ich planowany zakres to:

### Wind

- podstawowy katalog turbin jest pierwszym zaimplementowanym zakresem tego
  modułu;
- źródło danych wiatrowych;
- uproszczony godzinowy profil produkcji;
- rozmieszczanie turbin i minimalne odstępy;
- później adapter PyWake, AEP, profil po uwzględnieniu wake i raportowanie strat.

### Solar

- dane nasłonecznienia;
- adapter pvlib;
- rozmieszczanie instalacji PV;
- godzinowa produkcja energii.

### Storage

- model baterii i stan naładowania;
- ładowanie nadwyżką;
- rozładowanie zgodnie z ograniczeniami;
- uwzględnienie strat.

### Grid

- model wspólnego przyłączenia;
- limit przyłączenia;
- wykorzystanie przyłącza i ograniczenia eksportu.

### Hybrid

- agregacja wyników wind, solar i storage;
- curtailment przy ograniczonym przyłączu;
- porównywanie scenariuszy hybrydowych wiatr + PV + magazyn.

Kolejność etapów i zakres prac szczegółowych określa [ROADMAP.md](ROADMAP.md).

## Pochodzenie i wersjonowanie danych

- Każda warstwa przestrzenna musi mieć źródło oraz stabilną wersję, datę lub
  identyfikator zbioru danych.
- Każda reguła musi mieć identyfikator, wersję, podstawę, okres obowiązywania
  oraz technologię, której dotyczy.
- Wynik analizy musi zapisywać wersje użytych warstw i reguł razem z datą,
  parametrami i identyfikatorem przebiegu.
- Raport musi przedstawiać źródła i wersje danych, aby wynik był odtwarzalny.
- Sama obecność wersji nie potwierdza aktualności, kompletności, dokładności
  ani poprawności danych. Użytkownik musi zweryfikować te cechy przed użyciem
  wyniku.
- Reguły prawne są danymi konfiguracyjnymi; nie wolno utrwalać bieżących
  wymagań prawnych bezpośrednio w algorytmach.

## Ograniczenia obecnego MVP

Obecne MVP:

- korzysta wyłącznie z dostarczonych plików GeoJSON i YAML;
- nie pobiera automatycznie danych i nie ocenia, czy zewnętrzne warstwy są
  kompletne dla danej lokalizacji;
- nie wykonuje końcowej kwalifikacji prawnej, środowiskowej, planistycznej,
  technicznej ani przyłączeniowej;
- udostępnia tylko interfejs CLI, bez mapy i interfejsu webowego;
- nie zawiera katalogu turbin, danych wiatrowych, produkcji energii,
  rozmieszczania turbin ani modelu wake;
- nie zawiera jeszcze modułów solar, storage, grid ani hybrid.

Wynik screeningu jest materiałem pomocniczym. Nie stanowi wiążącej opinii
prawnej, decyzji administracyjnej, gwarancji możliwości realizacji inwestycji
ani bankowalnej prognozy produkcji.

## Odpowiedzialność za dane i interpretację

Użytkownik odpowiada za wybór, aktualność, kompletność i jakość danych
wejściowych. Przykładowe reguły nie są aktualnymi wymaganiami prawnymi.
Wynik screeningu wymaga weryfikacji przez właściwych ekspertów i nie może być
przedstawiany jako wiążąca opinia prawna ani gwarancja realizacji inwestycji.
