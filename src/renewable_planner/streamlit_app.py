"""Thin Streamlit prototype for the spatial screening use case.

Run with:

    streamlit run src/renewable_planner/streamlit_app.py

This module keeps every piece of non-widget logic in plain, Streamlit-free
functions (``list_sample_rule_files``, ``run_screening``, ``area_summary``,
``findings_table``, ``render_schematic_map_svg``) so it can be unit tested
without a running Streamlit session. Only :func:`render_app` and its private
``_render_*`` helpers call into ``streamlit`` (imported lazily, inside the
functions, so importing this module does not require the optional
``streamlit`` dependency to be installed).

Like the CLI, this view calls only existing use cases: screening is wired
through :mod:`renewable_planner.composition`, the same composition the CLI
uses, so no screening logic is duplicated between the two interfaces. No
GeoPandas or Shapely call happens in this module — the schematic map is
drawn from the GeoJSON coordinates that ``write_screening_outputs`` already
produces as plain data.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from renewable_planner.adapters.geospatial.file_screening import load_site, write_screening_outputs
from renewable_planner.application.spatial import ScreenSiteCommand, ScreenSiteError
from renewable_planner.composition import build_file_screen_site, build_text_report_generator
from renewable_planner.domain import ScreenSiteResult

DEFAULT_COUNTRY = "PL"
TECHNOLOGY_OPTIONS = ("wind",)
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

DISCLAIMER = (
    "Wynik służy wyłącznie do wstępnego screeningu; nie jest wiążącą opinią prawną, "
    "wymaga sprawdzenia aktualności danych i nie gwarantuje możliwości realizacji inwestycji."
)


class ScreeningRequestError(ValueError):
    """Raised when the Streamlit request cannot be prepared or executed."""


@dataclass(frozen=True, slots=True)
class ScreeningOutcome:
    """Everything the view needs to render after a successful screening run."""

    result: ScreenSiteResult
    report_text: str
    available_area_geojson: Mapping[str, Any]
    excluded_areas_geojson: Mapping[str, Any]
    metadata_json: Mapping[str, Any]


def list_sample_rule_files() -> tuple[Path, ...]:
    """Return the bundled sample rule configuration files, sorted by name."""
    if not CONFIG_DIR.is_dir():
        return ()
    return tuple(sorted(CONFIG_DIR.glob("*.yaml")))


def run_screening(
    site_path: Path,
    constraints_path: Path,
    rules_path: Path,
    technology: str,
    output_directory: Path,
    country: str = DEFAULT_COUNTRY,
    analysis_date: date | None = None,
) -> ScreeningOutcome:
    """Run the ``ScreenSite`` use case and prepare everything the view needs.

    Wires the same :mod:`renewable_planner.composition` helpers as the CLI,
    so screening and reporting logic is defined once and shared, not
    duplicated between interfaces.
    """
    if not technology.strip():
        raise ScreeningRequestError("technology must not be empty")
    try:
        site = load_site(site_path)
        use_case, project = build_file_screen_site(site, site_path, constraints_path, rules_path)
        result = use_case.execute(
            ScreenSiteCommand(
                project_id=project.id,
                site_id=site.id,
                country=country,
                technology=technology,
                analysis_date=analysis_date or date.today(),
            )
        )
    except (ScreenSiteError, ValueError, OSError) as error:
        raise ScreeningRequestError(str(error)) from error

    write_screening_outputs(result, output_directory)
    report = build_text_report_generator().execute(project, result)
    (output_directory / "report.txt").write_text(report, encoding="utf-8")

    return ScreeningOutcome(
        result=result,
        report_text=report,
        available_area_geojson=_read_json(output_directory / "available_area.geojson"),
        excluded_areas_geojson=_read_json(output_directory / "excluded_areas.geojson"),
        metadata_json=_read_json(output_directory / "metadata.json"),
    )


def area_summary(outcome: ScreeningOutcome) -> dict[str, float]:
    """Return the area summary the CLI also prints, keyed for display."""
    spatial = outcome.result.spatial_result
    return {
        "Powierzchnia początkowa (m²)": spatial.initial_area_square_meters,
        "Powierzchnia wykluczona (m²)": spatial.excluded_area_square_meters,
        "Powierzchnia dostępna (m²)": spatial.available_area_square_meters,
    }


def findings_table(outcome: ScreeningOutcome) -> list[dict[str, str]]:
    """Return one display-ready row per finding (the "collisions" list)."""
    return [
        {
            "reguła": str(finding.constraint_id),
            "poziom": finding.level.value,
            "status": finding.status.value,
            "źródło": finding.data_source,
            "wersja": finding.data_version,
            "komunikat": finding.message,
        }
        for finding in outcome.result.spatial_result.findings
    ]


def render_schematic_map_svg(
    layers: Sequence[tuple[Mapping[str, Any], str]],
    size: int = 480,
) -> str:
    """Render GeoJSON polygon layers as a flat schematic SVG.

    This intentionally is not a georeferenced basemap (the CRS is not
    considered): it plots the site's own coordinates as a simple shape
    diagram, which is enough for a first, "thin" prototype without adding a
    mapping library or projecting anything in the view. ``layers`` pairs a
    GeoJSON ``FeatureCollection`` with the fill/stroke color to draw it in.
    Returns an empty string when there is nothing to draw.
    """
    layer_rings: list[tuple[list[list[tuple[float, float]]], str]] = []
    all_points: list[tuple[float, float]] = []
    for collection, color in layers:
        rings: list[list[tuple[float, float]]] = []
        for feature in collection.get("features", []):
            rings.extend(_polygon_rings(feature.get("geometry", {})))
        layer_rings.append((rings, color))
        for ring in rings:
            all_points.extend(ring)

    if not all_points:
        return ""

    min_x = min(x for x, _ in all_points)
    max_x = max(x for x, _ in all_points)
    min_y = min(y for _, y in all_points)
    max_y = max(y for _, y in all_points)
    span = max(max_x - min_x, max_y - min_y, 1e-9)
    scale = (size - 20) / span
    margin = 10.0

    def project(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (margin + (x - min_x) * scale, margin + (max_y - y) * scale)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">'
    ]
    for rings, color in layer_rings:
        if not rings:
            continue
        path_data = " ".join(_ring_path([project(point) for point in ring]) for ring in rings)
        parts.append(
            f'<path d="{path_data}" fill="{color}" fill-opacity="0.55" '
            f'stroke="{color}" stroke-width="1.5" fill-rule="evenodd" />'
        )
    parts.append("</svg>")
    return "".join(parts)


def _polygon_rings(geometry: Mapping[str, Any]) -> list[list[tuple[float, float]]]:
    """Return every linear ring (exterior and holes) as ``(x, y)`` tuples."""
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        polygons: Sequence[Any] = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates or ()
    else:
        return []
    return [
        [(float(point[0]), float(point[1])) for point in ring]
        for polygon in polygons
        for ring in polygon
    ]


def _ring_path(points: Sequence[tuple[float, float]]) -> str:
    if not points:
        return ""
    head = f"M {points[0][0]:.2f} {points[0][1]:.2f}"
    tail = " ".join(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return f"{head} {tail} Z"


def _read_json(path: Path) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], json.loads(path.read_text(encoding="utf-8")))


def render_app() -> None:  # pragma: no cover - exercised only via `streamlit run`
    """Render the Streamlit UI. Contains only widget wiring, no business logic."""
    import streamlit as st

    st.set_page_config(page_title="DonQuixote — screening OZE", layout="wide")
    st.title("DonQuixote — wstępny screening terenu")
    st.caption(DISCLAIMER)

    site_file = st.file_uploader("Granica terenu (GeoJSON)", type=["geojson", "json"])
    constraints_file = st.file_uploader("Warstwy ograniczeń (GeoJSON)", type=["geojson", "json"])
    technology = st.selectbox("Technologia", options=TECHNOLOGY_OPTIONS)

    rule_files = list_sample_rule_files()
    if not rule_files:
        st.warning("Nie znaleziono przykładowych zestawów reguł w katalogu config/.")
        return
    rules_path = st.selectbox(
        "Przykładowy zestaw reguł", options=rule_files, format_func=lambda path: path.name
    )

    run_clicked = st.button("Uruchom screening", disabled=not (site_file and constraints_file))

    if run_clicked:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            site_path = tmp_dir / "site.geojson"
            constraints_path = tmp_dir / "constraints.geojson"
            site_path.write_bytes(site_file.getvalue())
            constraints_path.write_bytes(constraints_file.getvalue())
            try:
                st.session_state["outcome"] = run_screening(
                    site_path, constraints_path, rules_path, technology, tmp_dir / "output"
                )
                st.session_state.pop("error", None)
            except ScreeningRequestError as error:
                st.session_state["error"] = str(error)
                st.session_state.pop("outcome", None)

    if error_message := st.session_state.get("error"):
        st.error(error_message)

    outcome = st.session_state.get("outcome")
    if outcome is not None:
        _render_outcome(outcome)


def _render_outcome(outcome: ScreeningOutcome) -> None:  # pragma: no cover - UI wiring
    import streamlit as st

    st.subheader("Podsumowanie powierzchni")
    columns = st.columns(3)
    for column, (label, value) in zip(columns, area_summary(outcome).items(), strict=True):
        column.metric(label, f"{value:.2f}")

    st.subheader("Lista kolizji (findingi)")
    rows = findings_table(outcome)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Nie wykryto żadnych kolizji.")

    st.subheader("Mapa (schematyczna, bez podkładu geograficznego)")
    svg = render_schematic_map_svg(
        [
            (outcome.available_area_geojson, "#2e9f43"),
            (outcome.excluded_areas_geojson, "#d62728"),
        ]
    )
    if svg:
        st.markdown(svg, unsafe_allow_html=True)
        st.caption("Zielony: obszar dostępny. Czerwony: obszar wykluczony.")
    else:
        st.info("Brak geometrii do wyświetlenia.")

    st.subheader("Pobierz wyniki")
    download_columns = st.columns(4)
    download_columns[0].download_button("report.txt", outcome.report_text, file_name="report.txt")
    download_columns[1].download_button(
        "metadata.json",
        json.dumps(outcome.metadata_json, indent=2, ensure_ascii=False),
        file_name="metadata.json",
    )
    download_columns[2].download_button(
        "available_area.geojson",
        json.dumps(outcome.available_area_geojson, indent=2),
        file_name="available_area.geojson",
    )
    download_columns[3].download_button(
        "excluded_areas.geojson",
        json.dumps(outcome.excluded_areas_geojson, indent=2),
        file_name="excluded_areas.geojson",
    )


if __name__ == "__main__":  # pragma: no cover - exercised only via `streamlit run`
    render_app()
