"""Plain-text analysis report adapter."""

from renewable_planner.domain.battery_dispatch import BatteryDispatchResult
from renewable_planner.domain.constraint_finding import ConstraintFinding, FindingStatus
from renewable_planner.domain.hybrid_production import HybridProductionResult
from renewable_planner.domain.solar_simulation import SolarSimulationResult
from renewable_planner.domain.spatial_constraint import ConstraintLevel
from renewable_planner.domain.wind_simulation import WindSimulationResult
from renewable_planner.ports.reporting import AnalysisReportGenerator, AnalysisReportRequest

DISCLAIMER = (
    "Wynik służy wyłącznie do wstępnego screeningu; nie jest wiążącą opinią prawną, "
    "wymaga sprawdzenia aktualności danych i nie gwarantuje możliwości realizacji inwestycji."
)


class TextAnalysisReportGenerator(AnalysisReportGenerator):
    """Render a screening result as a human-readable UTF-8 text report."""

    def generate(self, request: AnalysisReportRequest) -> str:
        run = request.result.analysis_run
        spatial = request.result.spatial_result
        parameters = dict(run.parameters)
        technology = run.technology or parameters.get("technology", "nie określono")

        lines = [
            "RAPORT WSTĘPNEGO SCREENINGU TERENU",
            "===================================",
            "",
            "INFORMACJE O ANALIZIE",
            f"Nazwa projektu: {request.project.name}",
            f"Identyfikator analizy: {run.id}",
            f"Data uruchomienia: {run.created_at.isoformat()}",
            f"Technologia: {technology}",
            "",
            "ŹRÓDŁA I WERSJE DANYCH",
        ]
        lines.extend(
            f"- {name}: {version}" for name, version in (run.data_versions or (("brak", "brak"),))
        )
        lines.extend(["", "ZASTOSOWANE REGUŁY"])
        if spatial.findings:
            lines.extend(self._rule_line(finding) for finding in spatial.findings)
        else:
            lines.append("- Brak zastosowanych reguł.")

        exclusions = tuple(
            finding
            for finding in spatial.findings
            if finding.level is ConstraintLevel.EXCLUSION
            and finding.status is FindingStatus.AFFECTED
        )
        warnings = tuple(
            finding
            for finding in spatial.findings
            if finding.level in {ConstraintLevel.WARNING, ConstraintLevel.CONDITIONAL}
            and finding.status is FindingStatus.AFFECTED
        )
        lines.extend(["", "WYKRYTE WYKLUCZENIA"])
        lines.extend(self._finding_line(finding) for finding in exclusions)
        if not exclusions:
            lines.append("- Nie wykryto.")
        lines.extend(["", "OSTRZEŻENIA"])
        lines.extend(self._finding_line(finding) for finding in warnings)
        if not warnings:
            lines.append("- Nie wykryto.")

        lines.extend(
            [
                "",
                "PODSUMOWANIE POWIERZCHNI",
                f"Powierzchnia początkowa: {spatial.initial_area_square_meters:.2f} m²",
                f"Powierzchnia wykluczona: {spatial.excluded_area_square_meters:.2f} m²",
                f"Powierzchnia dostępna: {spatial.available_area_square_meters:.2f} m²",
            ]
        )
        lines.extend(["", "PRODUKCJA ENERGII (WIATR)"])
        lines.extend(self._wind_production_lines(request.wind_simulation_result))
        lines.extend(["", "PRODUKCJA ENERGII (PV)"])
        lines.extend(self._solar_production_lines(request.solar_simulation_result))
        lines.extend(["", "AGREGACJA HYBRYDOWA I PRZYŁĄCZE"])
        lines.extend(self._hybrid_production_lines(request.hybrid_result))
        lines.extend(["", "MAGAZYN ENERGII (BATERIA)"])
        lines.extend(self._battery_dispatch_lines(request.battery_dispatch_result))
        lines.extend(
            [
                "",
                "OGRANICZENIA WYNIKU",
                f"- {DISCLAIMER}",
                "- Wynik wymaga weryfikacji przez właściwych ekspertów i na podstawie "
                "aktualnych danych.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _wind_production_lines(wind_result: WindSimulationResult | None) -> list[str]:
        if wind_result is None:
            return ["- Symulacji produkcji energii wiatrowej nie uruchomiono w tym przebiegu."]
        no_wake_mwh = wind_result.no_wake_profile.total_energy_mwh
        with_wake_mwh = wind_result.wake_profile.total_energy_mwh
        return [
            f"AEP bez uwzględnienia wake: {no_wake_mwh:.2f} MWh",
            f"AEP z uwzględnieniem wake: {with_wake_mwh:.2f} MWh",
            f"Straty wake: {wind_result.wake_loss_mwh:.2f} MWh "
            f"({wind_result.wake_loss_fraction * 100:.2f}%)",
        ]

    @staticmethod
    def _solar_production_lines(solar_result: SolarSimulationResult | None) -> list[str]:
        if solar_result is None:
            return ["- Symulacji produkcji energii PV nie uruchomiono w tym przebiegu."]
        dc_mwh = solar_result.dc_profile.total_energy_mwh
        ac_mwh = solar_result.ac_profile.total_energy_mwh
        return [
            f"AEP DC (przed inwerterem): {dc_mwh:.2f} MWh",
            f"AEP AC (po inwerterze): {ac_mwh:.2f} MWh",
            f"Straty inwertera: {solar_result.inverter_loss_mwh:.2f} MWh "
            f"({solar_result.inverter_loss_fraction * 100:.2f}%)",
        ]

    @staticmethod
    def _hybrid_production_lines(hybrid_result: HybridProductionResult | None) -> list[str]:
        if hybrid_result is None:
            return ["- Agregacji hybrydowej i limitu przyłącza nie uruchomiono w tym przebiegu."]
        curtailment = hybrid_result.curtailment
        gross_mwh = hybrid_result.aggregate_profile.total_energy_mwh
        delivered_mwh = curtailment.delivered_profile.total_energy_mwh
        return [
            f"Produkcja łączna (przed ograniczeniem przyłącza): {gross_mwh:.2f} MWh",
            f"Dostarczone do sieci (po ograniczeniu przyłącza): {delivered_mwh:.2f} MWh",
            f"Curtailment: {curtailment.curtailed_energy_mwh:.2f} MWh "
            f"({curtailment.curtailed_energy_fraction * 100:.2f}%)",
            f"Wykorzystanie przyłącza: {curtailment.utilization_fraction * 100:.2f}%",
        ]

    @staticmethod
    def _battery_dispatch_lines(battery_result: BatteryDispatchResult | None) -> list[str]:
        if battery_result is None:
            return ["- Symulacji magazynu energii nie uruchomiono w tym przebiegu."]
        return [
            f"Naładowano: {battery_result.charged_energy_mwh:.2f} MWh",
            f"Rozładowano: {battery_result.discharged_energy_mwh:.2f} MWh",
            f"Straty magazynu: {battery_result.round_trip_loss_mwh:.2f} MWh",
            "Energia dostarczona po wsparciu magazynu: "
            f"{battery_result.delivered_profile.total_energy_mwh:.2f} MWh",
            f"Curtailment po wsparciu magazynu: {battery_result.curtailed_energy_mwh:.2f} MWh",
            f"Końcowy stan naładowania: {battery_result.final_state_of_charge_fraction * 100:.2f}%",
        ]

    @staticmethod
    def _rule_line(finding: ConstraintFinding) -> str:
        return (
            f"- {finding.constraint_id}: {finding.level.value}; "
            f"status={finding.status.value}; źródło={finding.data_source}; "
            f"wersja={finding.data_version}"
        )

    @staticmethod
    def _finding_line(finding: ConstraintFinding) -> str:
        return f"- {finding.message} (reguła {finding.constraint_id})"
