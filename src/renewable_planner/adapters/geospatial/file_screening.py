"""File adapters used to compose the spatial screening CLI."""

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from uuid import UUID, uuid5

import geopandas
from shapely import union_all
from shapely.geometry import mapping
from shapely.wkt import loads as load_wkt

from renewable_planner.adapters.rules import (
    RuleConfigurationError,
    SpatialRuleConfiguration,
    load_spatial_rule_configuration,
)
from renewable_planner.domain import (
    AnalysisRun,
    ConstraintCategory,
    ConstraintLevel,
    Project,
    ScreenSiteResult,
    Site,
    SpatialConstraint,
    SpatialDataLayer,
    SpatialGeometry,
)
from renewable_planner.ports.screening import (
    AnalysisRunRepository,
    ProjectRepository,
    SiteRepository,
    SiteScreeningResultRepository,
    SpatialDataLayerProvider,
    SpatialRuleProvider,
)

CLI_NAMESPACE = UUID("b1c9d594-f3cc-4d8a-8f74-fad5edb0a1b9")


class FileScreeningError(ValueError):
    """Raised when a CLI spatial input cannot be loaded or validated."""


class FileProjectRepository(ProjectRepository):
    def __init__(self, project: Project) -> None:
        self._project = project

    def get(self, project_id: UUID) -> Project | None:
        return self._project if project_id == self._project.id else None


class FileSiteRepository(SiteRepository):
    def __init__(self, site: Site) -> None:
        self._site = site

    def get(self, site_id: UUID) -> Site | None:
        return self._site if site_id == self._site.id else None


class MemoryAnalysisRunRepository(AnalysisRunRepository):
    def __init__(self) -> None:
        self.saved: list[AnalysisRun] = []

    def save(self, analysis_run: AnalysisRun) -> None:
        self.saved.append(analysis_run)


class JsonResultRepository(SiteScreeningResultRepository):
    def __init__(self) -> None:
        self.result: ScreenSiteResult | None = None

    def save(self, result: ScreenSiteResult) -> None:
        self.result = result


class YamlSpatialRuleProvider(SpatialRuleProvider):
    """Load versioned spatial rules from a YAML configuration file."""

    def __init__(self, path: Path) -> None:
        try:
            configurations = load_spatial_rule_configuration(path)
        except RuleConfigurationError as error:
            raise FileScreeningError(str(error)) from error
        self._rules = tuple(_to_domain_rule(configuration) for configuration in configurations)

    def get_active(
        self, country: str, technology: str, as_of: date
    ) -> tuple[SpatialConstraint, ...]:
        del country
        return tuple(
            rule for rule in self._rules if rule.applies_to(technology) and rule.is_active_on(as_of)
        )


class GeoJsonConstraintLayerProvider(SpatialDataLayerProvider):
    """Load and group constraint features into named versioned layers."""

    def __init__(self, path: Path, expected_crs: str) -> None:
        self._layers = _load_layers(path, expected_crs)

    def get_layers(
        self,
        names: Sequence[str],
        boundary: SpatialGeometry,
        as_of: date,
    ) -> tuple[SpatialDataLayer, ...]:
        del as_of
        if boundary.crs != next(iter(self._layers.values())).geometry.crs:
            raise FileScreeningError("site and constraints must use the same CRS")
        try:
            return tuple(self._layers[name] for name in names)
        except KeyError as error:
            raise FileScreeningError(f"constraints layer is missing: {error.args[0]}") from error


def load_site(path: Path) -> Site:
    """Load a site through the existing boundary adapter contract."""
    from renewable_planner.adapters.geospatial.geojson_site_boundary import (
        GeoJsonSiteBoundaryProvider,
    )

    site_id = uuid5(CLI_NAMESPACE, str(path.resolve()))
    boundary = GeoJsonSiteBoundaryProvider({site_id: path}).get_boundary(site_id)
    return Site(id=site_id, name=path.stem, boundary=boundary)


def build_project(site: Site, site_path: Path) -> Project:
    return Project(
        id=uuid5(CLI_NAMESPACE, f"project:{site_path.resolve()}"),
        name=f"Screening {site.name}",
        site_ids=(site.id,),
    )


def write_screening_outputs(result: ScreenSiteResult, output_directory: Path) -> None:
    """Write trace metadata and the two spatial result layers."""
    output_directory.mkdir(parents=True, exist_ok=True)
    spatial = result.spatial_result
    metadata = {
        "analysis_run": {
            "id": str(result.analysis_run.id),
            "project_id": str(result.analysis_run.project_id),
            "site_id": str(result.analysis_run.site_id),
            "technology": result.analysis_run.technology,
            "country": result.analysis_run.country,
            "analysis_date": dict(result.analysis_run.parameters)["analysis_date"],
            "status": result.analysis_run.status.value,
        },
        "initial_area_square_meters": spatial.initial_area_square_meters,
        "excluded_area_square_meters": spatial.excluded_area_square_meters,
        "available_area_square_meters": spatial.available_area_square_meters,
        "warnings": sum(
            finding.level is ConstraintLevel.WARNING and finding.status.value == "affected"
            for finding in spatial.findings
        ),
        "findings": [
            {
                "id": str(finding.id),
                "constraint_id": str(finding.constraint_id),
                "status": finding.status.value,
                "level": finding.level.value,
                "data_source": finding.data_source,
                "data_version": finding.data_version,
            }
            for finding in spatial.findings
        ],
        "data_versions": dict(result.analysis_run.data_versions),
    }
    (output_directory / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_geometry(output_directory / "available_area.geojson", spatial.remaining_geometry)
    _write_geometry(output_directory / "excluded_areas.geojson", spatial.excluded_geometry)


def _load_layers(path: Path, expected_crs: str) -> dict[str, SpatialDataLayer]:
    try:
        frame = geopandas.read_file(path)
    except Exception as error:
        raise FileScreeningError(f"cannot read constraints GeoJSON: {path}") from error
    if frame.empty or frame.crs is None:
        raise FileScreeningError("constraints must be non-empty and declare a CRS")
    actual_crs = frame.crs.to_authority()
    if actual_crs is None or f"{actual_crs[0]}:{actual_crs[1]}" != expected_crs:
        raise FileScreeningError(f"constraints must use {expected_crs}")
    required = {"layer", "source", "version"}
    if not required.issubset(frame.columns):
        missing = ", ".join(sorted(required - set(frame.columns)))
        raise FileScreeningError(f"constraints are missing properties: {missing}")
    layers: dict[str, SpatialDataLayer] = {}
    for name, layer_frame in frame.groupby("layer"):
        if not isinstance(name, str) or not name.strip():
            raise FileScreeningError("constraint layer names must not be empty")
        first = layer_frame.iloc[0]
        layers[name] = SpatialDataLayer(
            name=name,
            geometry=SpatialGeometry(union_all(layer_frame.geometry.tolist()).wkt, expected_crs),
            source=str(first["source"]),
            version=str(first["version"]),
        )
    return layers


def _to_domain_rule(configuration: SpatialRuleConfiguration) -> SpatialConstraint:
    return SpatialConstraint(
        id=configuration.id,
        name=configuration.name,
        category=ConstraintCategory.LEGAL,
        geometry=None,
        rule_version=f"yaml:{configuration.id}",
        source=configuration.legal_basis,
        valid_from=configuration.valid_from,
        valid_to=configuration.valid_to,
        level=configuration.severity,
        technologies=configuration.applies_to,
        required_layer=configuration.source_layer,
        buffer_meters=configuration.distance_m if configuration.operation == "buffer" else 0.0,
        operation=configuration.operation,
        legal_basis=configuration.legal_basis,
    )


def _write_geometry(path: Path, geometry: SpatialGeometry | None) -> None:
    features = []
    if geometry is not None:
        features.append(
            {"type": "Feature", "properties": {}, "geometry": mapping(load_wkt(geometry.wkt))}
        )
    document = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": geometry.crs if geometry else None}},
        "features": features,
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
