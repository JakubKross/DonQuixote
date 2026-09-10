# Wymagania projektu

## Cel

DonQuixote jest narzędziem wspomagającym wstępne planowanie instalacji OZE
w Polsce. Pierwsza wersja koncentrowała się na lądowych farmach wiatrowych;
obecna obejmuje też fotowoltaikę, magazyny energii i projekty hybrydowe
wiatr + PV + magazyn (patrz „Zaimplementowane moduły technologiczne” niżej).
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

### Moduł `wind` — katalog turbin, dane wiatrowe i produkcja

System musi:

- przechowywać producenta i nazwę modelu turbiny, moc znamionową w kW,
  średnicę wirnika, wysokość piasty w m, prędkości załączenia, znamionową i
  wyłączenia w m/s, uporządkowaną uproszczoną krzywą mocy w punktach m/s–kW
  oraz źródło i wersję danych;
- walidować jednostki wynikające z nazw pól oraz zakresy i skończoność
  wartości;
- odczytywać katalog turbin z YAML lub JSON i nie wymagać PyWake do
  utworzenia ani odczytu modelu turbiny;
- wczytywać godzinowy szereg czasowy zasobu wiatrowego (prędkość, kierunek)
  z pliku;
- generować rozmieszczenie turbin na dostępnym obszarze po screeningu, z
  zachowaniem minimalnych odstępów;
- symulować godzinowy profil produkcji wbudowanym, uproszczonym symulatorem
  (bez modelu wake) domyślnie;
- opcjonalnie (extra `pywake`) symulować produkcję adapterem PyWake z
  modelem wake, zwracać AEP z i bez uwzględnienia wake oraz raportować
  straty wake.

### Moduł `solar` — katalog PV, zasób i produkcja

System musi:

- przechowywać dane modułu PV (moc, sprawność, źródło i wersję danych) w
  katalogu YAML/JSON;
- dobrać wielkość instalacji PV na dostępnym obszarze po screeningu na
  podstawie zadanego współczynnika pokrycia terenu (ground coverage ratio);
- wczytywać godzinowy szereg czasowy zasobu nasłonecznienia (napromieniowanie
  w płaszczyźnie modułów, temperatura otoczenia) z pliku;
- symulować godzinową produkcję DC/AC wbudowanym, uproszczonym symulatorem
  domyślnie;
- opcjonalnie (extra `pvlib`) symulować produkcję adapterem pvlib z modelem
  inwertera PVWatts.

### Moduły `grid` i `hybrid` — przyłącze i agregacja

System musi:

- przyjmować limit mocy wspólnego przyłączenia;
- agregować profile produkcji wiatru i PV w jeden profil energii;
- ograniczać (curtailment) zagregowaną produkcję do limitu przyłącza i
  raportować wykorzystanie przyłącza oraz wielkość i udział curtailmentu.

### Moduł `storage` — magazyn energii

System musi:

- przechowywać dane baterii (pojemność, moc, sprawność ładowania/
  rozładowania, minimalny/maksymalny stan naładowania, źródło i wersję
  danych) w katalogu YAML/JSON;
- wyznaczać dyspozycję (dispatch) baterii względem zagregowanego profilu
  wiatr+PV i limitu przyłącza: ładowanie nadwyżką, rozładowanie zgodnie z
  ograniczeniami mocy i pojemności;
- uwzględniać straty magazynu (round-trip) i raportować końcowy stan
  naładowania oraz curtailment po wsparciu magazynu.

### Interfejsy

**CLI** udostępnia przypadek użycia screeningu poleceniem `screen-site` z
wymaganymi argumentami `--site`, `--constraints`, `--rules`, `--technology`,
`--output`; data analizy i kraj są konfigurowalne (domyślny kraj to Polska,
brak daty oznacza bieżącą datę). Symulacje wiatru/PV, agregacja hybrydowa i
magazyn są opcjonalne i włączane dodatkowymi flagami (pełna lista:
`donquixote screen-site --help`).

**Web (opcjonalnie, extra `web`/`streamlit`)** — proste API FastAPI
(`src/renewable_planner/api/`) i formularz Streamlit wywołują te same
przypadki użycia co CLI przez wspólny `composition`. Zakres i status
poszczególnych kroków wersji webowej (PostGIS, worker, frontend
React/MapLibre) opisuje [WEB_ARCHITECTURE.md](WEB_ARCHITECTURE.md).

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

Poniższe funkcje nie są jeszcze zaimplementowane:

- automatyczne pobieranie urzędowych danych przestrzennych i ocena ich
  kompletności dla danej lokalizacji;
- trwałe repozytoria danych (PostGIS) — API webowe i Streamlit korzystają
  obecnie z adapterów plikowych i repozytoriów w pamięci, które nie
  przetrwają restartu procesu;
- procesy robocze (worker) dla długich analiz uruchamianych przez API;
- realny interfejs mapowy z podkładem geograficznym (frontend
  React + MapLibre) — Streamlit ma na razie schematyczny podgląd SVG bez
  georeferencji;
- porównywanie scenariuszy hybrydowych obok siebie;
- końcowa kwalifikacja prawna, środowiskowa, planistyczna lub przyłączeniowa.

Szczegółowy status wersji webowej (kroki 1–5) opisuje
[WEB_ARCHITECTURE.md](WEB_ARCHITECTURE.md#9-status-implementacji), a
kolejność etapów i zakres prac — [ROADMAP.md](ROADMAP.md).

## Zaimplementowane moduły technologiczne

Moduły `wind`, `solar`, `storage`, `grid` i `hybrid` pozostają niezależne i
wymieniają wyniki przez wspólny model `EnergyProfile` — ich szczegółowy
zakres opisują sekcje wyżej („Moduł `wind`…”, „Moduł `solar`…”, „Moduły
`grid` i `hybrid`…”, „Moduł `storage`…”). Kolejność, w jakiej powstały, i
zakres pozostałych prac (przede wszystkim Etap 8 — wersja webowa) opisuje
[ROADMAP.md](ROADMAP.md).

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

Obecna wersja:

- korzysta wyłącznie z dostarczonych plików GeoJSON i YAML — nie pobiera
  automatycznie danych i nie ocenia, czy zewnętrzne warstwy są kompletne dla
  danej lokalizacji;
- nie wykonuje końcowej kwalifikacji prawnej, środowiskowej, planistycznej,
  technicznej ani przyłączeniowej;
- zakłada jeden, stały szereg czasowy zasobu wiatru/nasłonecznienia dla
  całego obszaru (brak przestrzennego zróżnicowania zasobu w obrębie farmy);
- używa katalogów turbin/PV/baterii zawierających wyłącznie dane dostarczone
  w konfiguracji — brak urzędowego katalogu producentów;
- bez zainstalowanych opcjonalnych extrasów (`pywake`, `pvlib`) używa
  wbudowanych, uproszczonych symulatorów — bez modelu wake i bez modelu
  inwertera PVWatts;
- API webowe i repozytoria w pamięci to jawny, wczesny krok (Krok 1 w
  [WEB_ARCHITECTURE.md](WEB_ARCHITECTURE.md)) — stan nie przetrwa restartu
  procesu i nie jest współdzielony między procesami roboczymi;
- nie ma jeszcze realnego interfejsu mapowego (React/MapLibre) — dostępne są
  CLI, proste API i formularz Streamlit ze schematycznym podglądem SVG.

Wynik screeningu jest materiałem pomocniczym. Nie stanowi wiążącej opinii
prawnej, decyzji administracyjnej, gwarancji możliwości realizacji inwestycji
ani bankowalnej prognozy produkcji.

## Odpowiedzialność za dane i interpretację

Użytkownik odpowiada za wybór, aktualność, kompletność i jakość danych
wejściowych. Przykładowe reguły nie są aktualnymi wymaganiami prawnymi.
Wynik screeningu wymaga weryfikacji przez właściwych ekspertów i nie może być
przedstawiany jako wiążąca opinia prawna ani gwarancja realizacji inwestycji.
