"""First application-level spatial rule engine."""

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from renewable_planner.domain.common import SpatialGeometry, require_non_empty
from renewable_planner.domain.constraint_finding import ConstraintFinding, FindingStatus
from renewable_planner.domain.spatial_constraint import ConstraintLevel, SpatialConstraint
from renewable_planner.domain.spatial_screening import (
    SpatialDataLayer,
    SpatialRuleEngineResult,
)
from renewable_planner.ports.spatial import SpatialOperations


class SpatialRuleEngine:
    """Evaluate configured spatial rules using a GIS operations port."""

    def __init__(self, spatial_operations: SpatialOperations) -> None:
        self._operations = spatial_operations

    def evaluate(
        self,
        site: SpatialGeometry,
        rules: Sequence[SpatialConstraint],
        layers: Mapping[str, SpatialDataLayer],
        technology: str,
        analysis_date: date,
        analysis_run_id: UUID | None = None,
    ) -> SpatialRuleEngineResult:
        """Apply active, technology-specific rules and summarize their impact."""
        require_non_empty(technology, "technology")
        run_id = analysis_run_id or uuid4()
        analyzed_at = datetime.combine(analysis_date, time.min, tzinfo=UTC)
        initial_area = self._operations.area_square_meters(site)
        findings: list[ConstraintFinding] = []
        exclusions: list[SpatialGeometry] = []

        for rule in rules:
            if not rule.is_active_on(analysis_date) or not rule.applies_to(technology):
                continue
            layer = self._resolve_layer(rule, layers)
            affected_geometry = self._affected_geometry(site, layer.geometry, rule.buffer_meters)
            findings.append(self._finding(run_id, rule, layer, analyzed_at, affected_geometry))
            if rule.level is ConstraintLevel.EXCLUSION and affected_geometry is not None:
                exclusions.append(affected_geometry)

        excluded_geometry = self._operations.union(exclusions)
        remaining_geometry = (
            site
            if excluded_geometry is None
            else self._operations.difference(site, excluded_geometry)
        )
        excluded_area = (
            0.0
            if excluded_geometry is None
            else self._operations.area_square_meters(excluded_geometry)
        )
        available_area = (
            0.0
            if remaining_geometry is None
            else self._operations.area_square_meters(remaining_geometry)
        )
        return SpatialRuleEngineResult(
            findings=tuple(findings),
            excluded_geometry=excluded_geometry,
            remaining_geometry=remaining_geometry,
            initial_area_square_meters=initial_area,
            excluded_area_square_meters=excluded_area,
            available_area_square_meters=available_area,
        )

    @staticmethod
    def _resolve_layer(
        rule: SpatialConstraint,
        layers: Mapping[str, SpatialDataLayer],
    ) -> SpatialDataLayer:
        if rule.required_layer is None:
            if rule.geometry is None:
                raise ValueError("rule has neither a required layer nor embedded geometry")
            return SpatialDataLayer(
                name=f"embedded:{rule.id}",
                geometry=rule.geometry,
                source=rule.source,
                version=rule.rule_version,
            )
        try:
            layer = layers[rule.required_layer]
        except KeyError as error:
            raise ValueError(f"missing required spatial layer: {rule.required_layer}") from error
        if layer.name != rule.required_layer:
            raise ValueError("spatial layer mapping key must match layer name")
        return layer

    def _affected_geometry(
        self,
        site: SpatialGeometry,
        layer_geometry: SpatialGeometry,
        buffer_meters: float,
    ) -> SpatialGeometry | None:
        evaluated_geometry = layer_geometry
        if buffer_meters > 0:
            evaluated_geometry = self._operations.buffer_meters(layer_geometry, buffer_meters)
        return self._operations.intersection(site, evaluated_geometry)

    @staticmethod
    def _finding(
        analysis_run_id: UUID,
        rule: SpatialConstraint,
        layer: SpatialDataLayer,
        analyzed_at: datetime,
        affected_geometry: SpatialGeometry | None,
    ) -> ConstraintFinding:
        affected = affected_geometry is not None
        status = FindingStatus.AFFECTED if affected else FindingStatus.NOT_AFFECTED
        outcome = "affects the analyzed site" if affected else "does not affect the analyzed site"
        message = f"Rule '{rule.name}' ({rule.level.value}) {outcome}."
        return ConstraintFinding(
            analysis_run_id=analysis_run_id,
            constraint_id=rule.id,
            status=status,
            message=message,
            analyzed_at=analyzed_at,
            affected_geometry=affected_geometry,
            level=rule.level,
            data_source=layer.source,
            data_version=layer.version,
            requires_expert_review=rule.level
            in {ConstraintLevel.CONDITIONAL, ConstraintLevel.WARNING},
        )
