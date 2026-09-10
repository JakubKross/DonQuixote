"""YAML and JSON adapter for hourly solar-resource time series."""

import json
import math
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from renewable_planner.domain import SolarResourceSample, SolarResourceTimeSeries


class SolarResourceFileError(ValueError):
    """Raised when a solar-resource file cannot be loaded or validated."""


def load_solar_resource_time_series(path: Path) -> SolarResourceTimeSeries:
    """Load an hourly solar-resource series from a YAML or JSON file.

    The supported document shape is ``{"source": str, "version": str,
    "records": [{"timestamp": str, "poa_irradiance_w_per_m2": float,
    "ambient_temperature_c": float}]}``. Values in the repository and tests
    are synthetic unless a source is explicitly provided by the caller.
    """
    document = _read_document(path)
    if not isinstance(document, Mapping):
        raise SolarResourceFileError("document must be a mapping")
    records = document.get("records")
    if not isinstance(records, list):
        raise SolarResourceFileError("document.records must be a list")
    try:
        samples = tuple(
            _parse_record(item, f"records[{index}]") for index, item in enumerate(records)
        )
        return SolarResourceTimeSeries(
            samples=samples,
            source=_text(document, "source", "document"),
            version=_text(document, "version", "document"),
        )
    except SolarResourceFileError:
        raise
    except ValueError as error:
        raise SolarResourceFileError(str(error)) from error


class SolarResourceFileProvider:
    """File-backed :class:`SolarResourceProvider` adapter.

    The file is read once, eagerly, when the adapter is constructed so that
    a malformed file fails fast during CLI composition rather than mid-run.
    """

    def __init__(self, path: Path) -> None:
        self._series = load_solar_resource_time_series(path)

    def get_time_series(self) -> SolarResourceTimeSeries:
        """Return the hourly irradiance and temperature series with provenance."""
        return self._series


def _read_document(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SolarResourceFileError(f"cannot read solar-resource file: {path}") from error
    if path.suffix.lower() == ".json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise SolarResourceFileError(f"cannot parse solar-resource file: {path}") from error
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError as error:
            raise SolarResourceFileError(f"cannot parse solar-resource file: {path}") from error
    raise SolarResourceFileError("solar-resource path must have a .json, .yaml or .yml suffix")


def _parse_record(value: object, path: str) -> SolarResourceSample:
    if not isinstance(value, Mapping):
        raise SolarResourceFileError(f"{path} must be a mapping")
    timestamp_text = value.get("timestamp")
    if not isinstance(timestamp_text, str) or not timestamp_text.strip():
        raise SolarResourceFileError(f"{path}.timestamp must be non-empty text")
    try:
        timestamp = datetime.fromisoformat(timestamp_text.strip())
    except ValueError as error:
        raise SolarResourceFileError(f"{path}.timestamp must be an ISO-8601 datetime") from error
    try:
        return SolarResourceSample(
            timestamp=timestamp,
            poa_irradiance_w_per_m2=_number(value, "poa_irradiance_w_per_m2", path),
            ambient_temperature_c=_number(value, "ambient_temperature_c", path),
        )
    except ValueError as error:
        raise SolarResourceFileError(f"{path}: {error}") from error


def _text(value: Mapping[str, Any], field: str, path: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise SolarResourceFileError(f"{path}.{field} must be non-empty text")
    return item.strip()


def _number(value: Mapping[str, Any], field: str, path: str) -> float:
    item = value.get(field)
    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
        raise SolarResourceFileError(f"{path}.{field} must be a finite number")
    return float(item)
