"""YAML and JSON adapter for the battery catalogue."""

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from renewable_planner.domain import Battery, BatteryCatalog


class BatteryCatalogError(ValueError):
    """Raised when a battery catalogue file cannot be loaded or validated."""


def load_battery_catalog(path: Path) -> BatteryCatalog:
    """Load a catalogue from a YAML or JSON file.

    The supported document shape is ``{"batteries": [{...}]}``. Catalogue
    values in the repository and tests are synthetic unless a source is
    explicitly provided by the caller.
    """
    document = _read_document(path)
    if not isinstance(document, Mapping) or not isinstance(document.get("batteries"), list):
        raise BatteryCatalogError("document.batteries must be a list")
    try:
        batteries = tuple(
            _parse_battery(item, f"batteries[{index}]")
            for index, item in enumerate(document["batteries"])
        )
        return BatteryCatalog(batteries)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, BatteryCatalogError):
            raise
        raise BatteryCatalogError(str(error)) from error


def _read_document(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(raw)
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise BatteryCatalogError(f"cannot read catalogue: {path}") from error
    raise BatteryCatalogError("catalogue path must have a .json, .yaml or .yml suffix")


def _parse_battery(value: object, path: str) -> Battery:
    if not isinstance(value, Mapping):
        raise BatteryCatalogError(f"{path} must be a mapping")
    try:
        return Battery(
            manufacturer=_text(value, "manufacturer", path),
            model_name=_text(value, "model_name", path),
            capacity_mwh=_number(value, "capacity_mwh", path),
            max_charge_power_mw=_number(value, "max_charge_power_mw", path),
            max_discharge_power_mw=_number(value, "max_discharge_power_mw", path),
            round_trip_efficiency_percent=_number(value, "round_trip_efficiency_percent", path),
            min_state_of_charge_fraction=_number(value, "min_state_of_charge_fraction", path),
            max_state_of_charge_fraction=_number(value, "max_state_of_charge_fraction", path),
            data_source=_text(value, "data_source", path),
            data_version=_text(value, "data_version", path),
        )
    except BatteryCatalogError:
        raise
    except ValueError as error:
        raise BatteryCatalogError(f"{path}: {error}") from error


def _text(value: Mapping[str, Any], field: str, path: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise BatteryCatalogError(f"{path}.{field} must be non-empty text")
    return item.strip()


def _number(value: Mapping[str, Any], field: str, path: str) -> float:
    item = value.get(field)
    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
        raise BatteryCatalogError(f"{path}.{field} must be a finite number")
    return float(item)
