from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from renewable_planner.adapters.rules import (
    RuleConfigurationError,
    load_spatial_rule_configuration,
)

RULE = {
    "id": "40000000-0000-0000-0000-000000000001",
    "name": "Fikcyjna reguła",
    "severity": "exclusion",
    "applies_to": ["wind"],
    "source_layer": "buildings",
    "operation": "buffer",
    "distance_m": 25,
    "legal_basis": "synthetic-rule-v1",
    "valid_from": "2026-01-01",
    "valid_to": "2030-12-31",
}


def _write_rules(tmp_path: Path, rule: object) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump({"rules": [rule]}), encoding="utf-8")
    return path


def test_loads_typed_spatial_rule_configuration(tmp_path: Path) -> None:
    configuration = load_spatial_rule_configuration(_write_rules(tmp_path, RULE))[0]

    assert configuration.id == UUID(RULE["id"])
    assert configuration.name == "Fikcyjna reguła"
    assert configuration.severity.value == "exclusion"
    assert configuration.applies_to == frozenset({"wind"})
    assert configuration.source_layer == "buildings"
    assert configuration.operation == "buffer"
    assert configuration.distance_m == 25.0
    assert configuration.valid_from == date(2026, 1, 1)
    assert configuration.valid_to == date(2030, 12, 31)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", None, "is required"),
        ("severity", "critical", "unknown level"),
        ("distance_m", -1, "non-negative"),
        ("valid_from", "not-a-date", "YYYY-MM-DD"),
        ("applies_to", [], "at least one technology"),
        ("source_layer", "", "non-empty text"),
    ],
)
def test_reports_exact_invalid_rule_field(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    invalid_rule = dict(RULE)
    if value is None:
        del invalid_rule[field]
    else:
        invalid_rule[field] = value

    with pytest.raises(RuleConfigurationError) as raised:
        load_spatial_rule_configuration(_write_rules(tmp_path, invalid_rule))

    assert f"rules[0].{field}" in str(raised.value)
    assert message in str(raised.value)


def test_reports_valid_to_before_valid_from(tmp_path: Path) -> None:
    invalid_rule = dict(RULE, valid_to="2025-12-31")

    with pytest.raises(RuleConfigurationError, match=r"rules\[0\]\.valid_to"):
        load_spatial_rule_configuration(_write_rules(tmp_path, invalid_rule))


def test_safe_loader_does_not_execute_yaml_tags(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.yaml"
    path.write_text(
        "rules:\n  - !!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8"
    )

    with pytest.raises(RuleConfigurationError, match="cannot read YAML"):
        load_spatial_rule_configuration(path)
