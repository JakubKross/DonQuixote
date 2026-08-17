"""ScreenSite application use case."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from uuid import UUID

from renewable_planner.domain.analysis_run import AnalysisRun, AnalysisRunStatus
from renewable_planner.domain.common import require_non_empty
from renewable_planner.domain.project import Project
from renewable_planner.domain.site import Site
from renewable_planner.domain.spatial_constraint import SpatialConstraint
from renewable_planner.domain.spatial_screening import ScreenSiteResult, SpatialDataLayer
from renewable_planner.ports.screening import (
    AnalysisRunRepository,
    ProjectRepository,
    SiteRepository,
    SiteScreeningResultRepository,
    SpatialDataLayerProvider,
    SpatialRuleEvaluator,
    SpatialRuleProvider,
)


class ScreenSiteError(RuntimeError):
    """Base class for readable ScreenSite application errors."""


class ProjectNotFoundError(ScreenSiteError):
    """Raised when the requested project does not exist."""


class SiteNotFoundError(ScreenSiteError):
    """Raised when the requested site does not exist."""


class SiteNotInProjectError(ScreenSiteError):
    """Raised when the site is not assigned to the requested project."""


class ScreeningDataAccessError(ScreenSiteError):
    """Raised when an input repository or provider fails."""


class ScreeningExecutionError(ScreenSiteError):
    """Raised after a started screening run fails and is recorded."""

    def __init__(self, analysis_run_id: UUID, reason: str) -> None:
        self.analysis_run_id = analysis_run_id
        self.reason = reason
        super().__init__(f"screening run {analysis_run_id} failed: {reason}")


@dataclass(frozen=True, slots=True)
class ScreenSiteCommand:
    """Validated input for one site screening execution."""

    project_id: UUID
    site_id: UUID
    country: str
    technology: str
    analysis_date: date
    parameters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.country, "country")
        require_non_empty(self.technology, "technology")
        if len({name for name, _ in self.parameters}) != len(self.parameters):
            raise ValueError("parameters must not contain duplicate names")
        for name, value in self.parameters:
            require_non_empty(name, "parameter name")
            require_non_empty(value, f"parameter {name}")


class ScreenSite:
    """Coordinate a traceable spatial screening analysis."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        site_repository: SiteRepository,
        rule_provider: SpatialRuleProvider,
        layer_provider: SpatialDataLayerProvider,
        rule_evaluator: SpatialRuleEvaluator,
        analysis_run_repository: AnalysisRunRepository,
        result_repository: SiteScreeningResultRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._projects = project_repository
        self._sites = site_repository
        self._rules = rule_provider
        self._layers = layer_provider
        self._evaluator = rule_evaluator
        self._runs = analysis_run_repository
        self._results = result_repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, command: ScreenSiteCommand) -> ScreenSiteResult:
        """Execute screening and persist its lifecycle and standardized result."""
        project = self._get_project(command.project_id)
        site = self._get_site(command.site_id)
        if site.id not in project.site_ids:
            raise SiteNotInProjectError(f"site {site.id} is not assigned to project {project.id}")

        created_at = self._now()
        run = AnalysisRun(
            project_id=project.id,
            site_id=site.id,
            technology=command.technology.strip().lower(),
            country=command.country.strip().upper(),
            parameters=self._parameter_snapshot(command),
            status=AnalysisRunStatus.PENDING,
            created_at=created_at,
            started_at=None,
        )
        try:
            self._runs.save(run)
            run = run.start(self._now())
            self._runs.save(run)
        except Exception as error:
            raise ScreeningDataAccessError("could not create the analysis run") from error

        try:
            rules = self._rules.get_active(
                run.country or "", run.technology or "", command.analysis_date
            )
            layer_names = tuple(
                sorted({rule.required_layer for rule in rules if rule.required_layer is not None})
            )
            supplied_layers = self._layers.get_layers(
                layer_names, site.boundary, command.analysis_date
            )
            layers = self._layer_mapping(supplied_layers)
            run = replace(run, data_versions=self._version_snapshot(rules, supplied_layers))
            self._runs.save(run)
            spatial_result = self._evaluator.evaluate(
                site=site.boundary,
                rules=rules,
                layers=layers,
                technology=run.technology or "",
                analysis_date=command.analysis_date,
                analysis_run_id=run.id,
            )
            completed_run = run.complete(self._now())
            result = ScreenSiteResult(
                analysis_run=completed_run,
                spatial_result=spatial_result,
            )
            self._results.save(result)
            self._runs.save(completed_run)
            return result
        except Exception as error:
            failed_run = run.fail(self._safe_error_message(error), self._now())
            try:
                self._runs.save(failed_run)
            except Exception as persistence_error:
                raise ScreeningExecutionError(
                    run.id, "analysis failed and its failed status could not be saved"
                ) from persistence_error
            raise ScreeningExecutionError(
                run.id, failed_run.error_message or "unknown error"
            ) from error

    def _get_project(self, project_id: UUID) -> Project:
        try:
            project = self._projects.get(project_id)
        except Exception as error:
            raise ScreeningDataAccessError("could not load the project") from error
        if project is None:
            raise ProjectNotFoundError(f"project {project_id} was not found")
        return project

    def _get_site(self, site_id: UUID) -> Site:
        try:
            site = self._sites.get(site_id)
        except Exception as error:
            raise ScreeningDataAccessError("could not load the site") from error
        if site is None:
            raise SiteNotFoundError(f"site {site_id} was not found")
        return site

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _parameter_snapshot(command: ScreenSiteCommand) -> tuple[tuple[str, str], ...]:
        parameters = dict(command.parameters)
        parameters.update(
            {
                "analysis_date": command.analysis_date.isoformat(),
                "country": command.country.strip().upper(),
                "technology": command.technology.strip().lower(),
            }
        )
        return tuple(sorted(parameters.items()))

    @staticmethod
    def _layer_mapping(layers: tuple[SpatialDataLayer, ...]) -> Mapping[str, SpatialDataLayer]:
        mapping = {layer.name: layer for layer in layers}
        if len(mapping) != len(layers):
            raise ValueError("layer provider returned duplicate layer names")
        return mapping

    @staticmethod
    def _version_snapshot(
        rules: tuple[SpatialConstraint, ...],
        layers: tuple[SpatialDataLayer, ...],
    ) -> tuple[tuple[str, str], ...]:
        versions = [(f"rule:{rule.id}", rule.rule_version) for rule in rules]
        versions.extend((f"layer:{layer.name}", layer.version) for layer in layers)
        return tuple(sorted(versions))

    @staticmethod
    def _safe_error_message(error: Exception) -> str:
        message = str(error).strip()
        return message or error.__class__.__name__
