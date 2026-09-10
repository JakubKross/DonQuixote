"""YAML and JSON adapter for hourly wind-resource time series."""

import json
import math
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from renewable_planner.domain import WindResourceSample, WindResourceTimeSeries


class WindResourceFileError(ValueError):
    """Raised when a wind-resource file cannot be loaded or validated."""


def load_wind_resource_time_series(path: Path) -> WindResourceTimeSeries:
    """Load an hourly wind-resource series from a YAML or JSON file.

    The supported document shape is ``{"source": str, "version": str,
    "records": [{"timestamp": str, "wind_speed_mps": float,
    "wind_direction_deg": float}]}``. Values in the repository and tests are
    synthetic unless a source is explicitly provided by the caller.
    """
    document = _read_document(path)
    if not isinstance(document, Mapping):
        raise WindResourceFileError("document must be a mapping")
    records = document.get("records")
    if not isinstance(records, list):
        raise WindResourceFileError("document.records must be a list")
    try:
        samples = tuple(
            _parse_record(item, f"records[{index}]") for index, item in enumerate(records)
        )
        return WindResourceTimeSeries(
            samples=samples,
            source=_text(document, "source", "document"),
            version=_text(document, "version", "document"),
        )
    except WindResourceFileError:
        raise
    except ValueError as error:
        raise WindResourceFileError(str(error)) from error


class WindResourceFileProvider:
    """File-backed :class:`WindResourceProvider` adapter.

    The file is read once, eagerly, when the adapter is constructed so that a
    malformed file fails fast during CLI composition rather than mid-run.
    """

    def __init__(self, path: Path) -> None:
        self._series = load_wind_resource_time_series(path)

    def get_time_series(self) -> WindResourceTimeSeries:
        """Return the hourly wind speed and direction series with provenance."""
        return self._series


def _read_document(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise WindResourceFileError(f"cannot read wind-resource file: {path}") from error
    if path.suffix.lower() == ".json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise WindResourceFileError(f"cannot parse wind-resource file: {path}") from error
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError as error:
            raise WindResourceFileError(f"cannot parse wind-resource file: {path}") from error
    raise WindResourceFileError("wind-resource path must have a .json, .yaml or .yml suffix")


def _parse_record(value: object, path: str) -> WindResourceSample:
    if not isinstance(value, Mapping):
        raise WindResourceFileError(f"{path} must be a mapping")
    timestamp_text = value.get("timestamp")
    if not isinstance(timestamp_text, str) or not timestamp_text.strip():
        raise WindResourceFileError(f"{path}.timestamp must be non-empty text")
    try:
        timestamp = datetime.fromisoformat(timestamp_text.strip())
    except ValueError as error:
        raise WindResourceFileError(f"{path}.timestamp must be an ISO-8601 datetime") from error
    try:
        return WindResourceSample(
            timestamp=timestamp,
            wind_speed_mps=_number(value, "wind_speed_mps", path),
            wind_direction_deg=_number(value, "wind_direction_deg", path),
        )
    except ValueError as error:
        raise WindResourceFileError(f"{path}: {error}") from error


def _text(value: Mapping[str, Any], field: str, path: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise WindResourceFileError(f"{path}.{field} must be non-empty text")
    return item.strip()


def _number(value: Mapping[str, Any], field: str, path: str) -> float:
    item = value.get(field)
    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
        raise WindResourceFileError(f"{path}.{field} must be a finite number")
    return float(item)
