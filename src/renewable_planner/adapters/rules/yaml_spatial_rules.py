"""Typed and safe YAML configuration for spatial rules."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

import yaml

from renewable_planner.domain.spatial_constraint import ConstraintLevel


class RuleConfigurationError(ValueError):
    """A YAML rule configuration violates the supported schema."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True, slots=True)
class SpatialRuleConfiguration:
    """Validated, library-neutral representation of one YAML rule."""

    id: UUID
    name: str
    severity: ConstraintLevel
    applies_to: frozenset[str]
    source_layer: str
    operation: str
    distance_m: float
    legal_basis: str
    valid_from: date
    valid_to: date | None


_ALLOWED_OPERATIONS = frozenset({"intersects", "buffer"})


def load_spatial_rule_configuration(path: Path) -> tuple[SpatialRuleConfiguration, ...]:
    """Safely load and validate the ``rules`` YAML document."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise RuleConfigurationError("document", f"cannot read YAML: {error}") from error

    root = _mapping(document, "document")
    rules = root.get("rules")
    if not isinstance(rules, list):
        raise RuleConfigurationError("rules", "must be a list")
    return tuple(_parse_rule(item, f"rules[{index}]") for index, item in enumerate(rules))


def _parse_rule(value: object, path: str) -> SpatialRuleConfiguration:
    raw = _mapping(value, path)
    configuration = SpatialRuleConfiguration(
        id=_uuid(raw, "id", path),
        name=_text(raw, "name", path),
        severity=_severity(raw, "severity", path),
        applies_to=_technologies(raw, "applies_to", path),
        source_layer=_text(raw, "source_layer", path),
        operation=_operation(raw, "operation", path),
        distance_m=_distance(raw, "distance_m", path),
        legal_basis=_text(raw, "legal_basis", path),
        valid_from=_date(raw, "valid_from", path),
        valid_to=_optional_date(raw, "valid_to", path),
    )
    if configuration.valid_to is not None and configuration.valid_to < configuration.valid_from:
        raise RuleConfigurationError(f"{path}.valid_to", "must not precede valid_from")
    return configuration


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise RuleConfigurationError(path, "must be a mapping")
    return value


def _text(raw: Mapping[str, object], field: str, path: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RuleConfigurationError(f"{path}.{field}", "is required and must be non-empty text")
    return value.strip()


def _uuid(raw: Mapping[str, object], field: str, path: str) -> UUID:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RuleConfigurationError(f"{path}.{field}", "is required")
    try:
        return UUID(value)
    except ValueError as error:
        raise RuleConfigurationError(f"{path}.{field}", "must be a valid UUID") from error


def _severity(raw: Mapping[str, object], field: str, path: str) -> ConstraintLevel:
    value = _text(raw, field, path).lower()
    try:
        return ConstraintLevel(value)
    except ValueError as error:
        allowed = ", ".join(level.value for level in ConstraintLevel)
        raise RuleConfigurationError(
            f"{path}.{field}", f"unknown level {value!r}; expected one of: {allowed}"
        ) from error


def _technologies(raw: Mapping[str, object], field: str, path: str) -> frozenset[str]:
    value = raw.get(field)
    if not isinstance(value, list) or not value:
        raise RuleConfigurationError(f"{path}.{field}", "must contain at least one technology")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise RuleConfigurationError(f"{path}.{field}", "must contain non-empty text values")
    return frozenset(item.strip().lower() for item in value)


def _operation(raw: Mapping[str, object], field: str, path: str) -> str:
    value = _text(raw, field, path).lower()
    if value not in _ALLOWED_OPERATIONS:
        allowed = ", ".join(sorted(_ALLOWED_OPERATIONS))
        raise RuleConfigurationError(
            f"{path}.{field}", f"unknown operation {value!r}; expected one of: {allowed}"
        )
    return value


def _distance(raw: Mapping[str, object], field: str, path: str) -> float:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleConfigurationError(f"{path}.{field}", "must be a number in metres")
    distance = float(value)
    if not math.isfinite(distance) or distance < 0:
        raise RuleConfigurationError(f"{path}.{field}", "must be a non-negative finite number")
    return distance


def _date(raw: Mapping[str, object], field: str, path: str) -> date:
    value = raw.get(field)
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise RuleConfigurationError(f"{path}.{field}", "must use ISO format YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise RuleConfigurationError(f"{path}.{field}", "must use ISO format YYYY-MM-DD") from error


def _optional_date(raw: Mapping[str, object], field: str, path: str) -> date | None:
    if field not in raw or raw[field] is None:
        return None
    return _date(raw, field, path)
