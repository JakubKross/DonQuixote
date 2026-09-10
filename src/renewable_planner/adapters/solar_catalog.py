"""YAML and JSON adapter for the PV-module catalogue."""

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from renewable_planner.domain import SolarModule, SolarModuleCatalog


class SolarModuleCatalogError(ValueError):
    """Raised when a PV-module catalogue file cannot be loaded or validated."""


def load_solar_module_catalog(path: Path) -> SolarModuleCatalog:
    """Load a catalogue from a YAML or JSON file.

    The supported document shape is ``{"modules": [{...}]}``. Catalogue
    values in the repository and tests are synthetic unless a source is
    explicitly provided by the caller.
    """
    document = _read_document(path)
    if not isinstance(document, Mapping) or not isinstance(document.get("modules"), list):
        raise SolarModuleCatalogError("document.modules must be a list")
    try:
        modules = tuple(
            _parse_module(item, f"modules[{index}]")
            for index, item in enumerate(document["modules"])
        )
        return SolarModuleCatalog(modules)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, SolarModuleCatalogError):
            raise
        raise SolarModuleCatalogError(str(error)) from error


def _read_document(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(raw)
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise SolarModuleCatalogError(f"cannot read catalogue: {path}") from error
    raise SolarModuleCatalogError("catalogue path must have a .json, .yaml or .yml suffix")


def _parse_module(value: object, path: str) -> SolarModule:
    if not isinstance(value, Mapping):
        raise SolarModuleCatalogError(f"{path} must be a mapping")
    try:
        return SolarModule(
            manufacturer=_text(value, "manufacturer", path),
            model_name=_text(value, "model_name", path),
            rated_power_w=_number(value, "rated_power_w", path),
            width_m=_number(value, "width_m", path),
            height_m=_number(value, "height_m", path),
            temperature_coefficient_pct_per_c=_number(
                value, "temperature_coefficient_pct_per_c", path
            ),
            data_source=_text(value, "data_source", path),
            data_version=_text(value, "data_version", path),
        )
    except SolarModuleCatalogError:
        raise
    except ValueError as error:
        raise SolarModuleCatalogError(f"{path}: {error}") from error


def _text(value: Mapping[str, Any], field: str, path: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise SolarModuleCatalogError(f"{path}.{field} must be non-empty text")
    return item.strip()


def _number(value: Mapping[str, Any], field: str, path: str) -> float:
    item = value.get(field)
    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
        raise SolarModuleCatalogError(f"{path}.{field} must be a finite number")
    return float(item)
