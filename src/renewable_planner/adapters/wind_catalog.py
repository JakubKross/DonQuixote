"""YAML and JSON adapter for the wind-turbine catalogue."""

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from renewable_planner.domain import PowerCurvePoint, WindTurbine, WindTurbineCatalog


class WindTurbineCatalogError(ValueError):
    """Raised when a turbine catalogue file cannot be loaded or validated."""


def load_wind_turbine_catalog(path: Path) -> WindTurbineCatalog:
    """Load a catalogue from a YAML or JSON file.

    The supported document shape is ``{"turbines": [{...}]}``. Catalogue
    values in the repository and tests are synthetic unless a source is
    explicitly provided by the caller.
    """
    document = _read_document(path)
    if not isinstance(document, Mapping) or not isinstance(document.get("turbines"), list):
        raise WindTurbineCatalogError("document.turbines must be a list")
    try:
        turbines = tuple(
            _parse_turbine(item, f"turbines[{index}]")
            for index, item in enumerate(document["turbines"])
        )
        return WindTurbineCatalog(turbines)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, WindTurbineCatalogError):
            raise
        raise WindTurbineCatalogError(str(error)) from error


def _read_document(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(raw)
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise WindTurbineCatalogError(f"cannot read catalogue: {path}") from error
    raise WindTurbineCatalogError("catalogue path must have a .json, .yaml or .yml suffix")


def _parse_turbine(value: object, path: str) -> WindTurbine:
    if not isinstance(value, Mapping):
        raise WindTurbineCatalogError(f"{path} must be a mapping")
    curve = value.get("power_curve")
    if not isinstance(curve, list):
        raise WindTurbineCatalogError(f"{path}.power_curve must be a list")
    try:
        return WindTurbine(
            manufacturer=_text(value, "manufacturer", path),
            model_name=_text(value, "model_name", path),
            rated_power_kw=_number(value, "rated_power_kw", path),
            rotor_diameter_m=_number(value, "rotor_diameter_m", path),
            hub_height_m=_number(value, "hub_height_m", path),
            cut_in_wind_speed_mps=_number(value, "cut_in_wind_speed_mps", path),
            rated_wind_speed_mps=_number(value, "rated_wind_speed_mps", path),
            cut_out_wind_speed_mps=_number(value, "cut_out_wind_speed_mps", path),
            power_curve=tuple(
                _parse_curve_point(point, f"{path}.power_curve[{index}]")
                for index, point in enumerate(curve)
            ),
            data_source=_text(value, "data_source", path),
            data_version=_text(value, "data_version", path),
        )
    except WindTurbineCatalogError:
        raise
    except ValueError as error:
        raise WindTurbineCatalogError(f"{path}: {error}") from error


def _parse_curve_point(value: object, path: str) -> PowerCurvePoint:
    if not isinstance(value, Mapping):
        raise WindTurbineCatalogError(f"{path} must be a mapping")
    try:
        return PowerCurvePoint(
            wind_speed_mps=_number(value, "wind_speed_mps", path),
            power_kw=_number(value, "power_kw", path),
        )
    except ValueError as error:
        raise WindTurbineCatalogError(f"{path}: {error}") from error


def _text(value: Mapping[str, Any], field: str, path: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise WindTurbineCatalogError(f"{path}.{field} must be non-empty text")
    return item.strip()


def _number(value: Mapping[str, Any], field: str, path: str) -> float:
    item = value.get(field)
    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
        raise WindTurbineCatalogError(f"{path}.{field} must be a finite number")
    return float(item)
