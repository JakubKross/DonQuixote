# Instrukcje dla Codexa

## Cel

Rozwijaj program do wstępnego planowania instalacji OZE.
Aktualny priorytet to moduł farm wiatrowych.

Przed rozpoczęciem zadania przeczytaj:

1. docs/PROJECT_BRIEF.md
2. docs/REQUIREMENTS.md
3. docs/ARCHITECTURE.md
4. docs/DOMAIN_MODEL.md
5. docs/ROADMAP.md

## Zasady architektoniczne

- Zachowuj modularny monolit.
- Logika domenowa nie może importować FastAPI, Streamlit,
  GeoPandas, PyWake, pvlib ani kodu bazy danych.
- Biblioteki zewnętrzne ukrywaj za adapterami.
- Interfejs użytkownika może wywoływać wyłącznie przypadki użycia.
- Moduły wind, solar, storage i grid muszą pozostać od siebie niezależne.
- Moduł hybrid może łączyć ich wyniki przez wspólne modele domenowe.
- Przechowuj godzinowe profile energii, nie tylko wartości roczne.
- Nie implementuj mikroserwisów bez wyraźnego polecenia.

## Jakość kodu

- Używaj type hints.
- Stosuj małe funkcje i jednoznaczne nazwy.
- Nie używaj globalnego stanu.
- Dodawaj testy do każdej nowej logiki domenowej.
- Nie umieszczaj logiki biznesowej w kontrolerach API ani interfejsie.
- Nie dodawaj zależności bez uzasadnienia.
- Używaj pathlib zamiast ręcznego składania ścieżek.
- Waliduj CRS i jednostki danych przestrzennych.

## Dane prawne

- Nie zapisuj aktualnych wymagań prawnych na stałe w algorytmach.
- Reguły mają być wersjonowanymi danymi lub konfiguracją.
- Każdy wynik prawny musi wskazywać źródło, okres obowiązywania
  i datę przeprowadzenia analizy.
- System nie może określać wyniku jako wiążącej opinii prawnej.

## Polecenia

Instalacja:

    python -m pip install -e ".[dev]"

Testy:

    pytest

Formatowanie:

    ruff format .

Kontrola:

    ruff check .
    mypy src

## Sposób pracy

Przed większą zmianą:

1. Przedstaw krótki plan.
2. Wskaż pliki, które zostaną zmienione.
3. Zidentyfikuj decyzje architektoniczne.
4. Wykonuj zmianę małymi krokami.
5. Uruchom testy.
6. Podsumuj zmiany i znane ograniczenia.

Nie twórz całego programu w ramach jednego zadania.
Preferuj małe, możliwe do zweryfikowania etapy.