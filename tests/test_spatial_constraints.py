from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from renewable_planner.domain import (
    ConstraintCategory,
    ConstraintFinding,
    FindingStatus,
    SpatialConstraint,
    SpatialGeometry,
)


def test_constraint_carries_versioned_legal_source() -> None:
    constraint = SpatialConstraint(
        name="Obszar chroniony",
        category=ConstraintCategory.ENVIRONMENTAL,
        geometry=SpatialGeometry("POLYGON ((0 0, 1 0, 1 1, 0 0))", "EPSG:2180"),
        rule_version="2026-01",
        source="Rejestr przykładowy, wydanie 2026-01",
        valid_from=date(2026, 1, 1),
    )

    assert constraint.rule_version == "2026-01"
    assert constraint.source.startswith("Rejestr")


def test_affected_finding_requires_geometry() -> None:
    with pytest.raises(ValueError, match="affected_geometry"):
        ConstraintFinding(
            analysis_run_id=uuid4(),
            constraint_id=uuid4(),
            status=FindingStatus.AFFECTED,
            message="Wykryto przecięcie.",
            analyzed_at=datetime.now(UTC),
        )


def test_finding_defaults_to_expert_review() -> None:
    finding = ConstraintFinding(
        analysis_run_id=uuid4(),
        constraint_id=uuid4(),
        status=FindingStatus.INDETERMINATE,
        message="Brak wystarczających danych.",
    )

    assert finding.requires_expert_review is True
