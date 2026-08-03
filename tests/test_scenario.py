from uuid import uuid4

import pytest

from renewable_planner.domain import Scenario


def test_scenario_references_project_and_site() -> None:
    project_id = uuid4()
    site_id = uuid4()

    scenario = Scenario(project_id=project_id, site_id=site_id, name="Bazowy")

    assert scenario.project_id == project_id
    assert scenario.site_id == site_id


def test_scenario_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="name"):
        Scenario(project_id=uuid4(), site_id=uuid4(), name="")
