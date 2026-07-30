# Architektura

## Podejście

System ma być modularnym monolitem z architekturą portów i adapterów.

Logika domenowa musi być niezależna od:
- interfejsu użytkownika,
- bazy danych,
- bibliotek GIS,
- PyWake,
- pvlib,
- frameworka webowego.

## Warstwy

1. Domain
   - Project
   - Site
   - Scenario
   - EnergyAsset
   - SpatialConstraint
   - EnergyProfile
   - AnalysisRun

2. Application
   - przypadki użycia,
   - koordynacja analiz,
   - generowanie scenariuszy.

3. Ports
   - repozytoria,
   - źródła danych,
   - symulatory technologiczne,
   - optymalizatory,
   - generatory raportów.

4. Adapters
   - GeoPandas,
   - Rasterio,
   - PostGIS,
   - PyWake,
   - pvlib,
   - zewnętrzne API.

5. Interfaces
   - CLI,
   - prototyp Streamlit,
   - późniejsze API FastAPI,
   - późniejszy frontend webowy.

## Moduły technologiczne

- technologies/wind
- technologies/solar
- technologies/storage
- technologies/grid
- technologies/hybrid

Każda technologia powinna zwracać ustandaryzowany godzinowy
profil produkcji lub przepływu energii.

## Zasada dotycząca interfejsu

Interfejs nie może wykonywać bezpośrednio operacji GeoPandas,
PyWake ani zapytań do bazy.

Interfejs wywołuje przypadki użycia z warstwy application.