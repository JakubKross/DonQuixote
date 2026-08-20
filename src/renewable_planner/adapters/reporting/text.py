"""Plain-text analysis report adapter."""

from renewable_planner.domain.constraint_finding import ConstraintFinding, FindingStatus
from renewable_planner.domain.spatial_constraint import ConstraintLevel
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
    def _rule_line(finding: ConstraintFinding) -> str:
        return (
            f"- {finding.constraint_id}: {finding.level.value}; "
            f"status={finding.status.value}; źródło={finding.data_source}; "
            f"wersja={finding.data_version}"
        )

    @staticmethod
    def _finding_line(finding: ConstraintFinding) -> str:
        return f"- {finding.message} (reguła {finding.constraint_id})"
