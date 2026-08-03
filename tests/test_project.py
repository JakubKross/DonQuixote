from uuid import uuid4

import pytest

from renewable_planner.domain import Project


def test_project_assigns_site_without_duplicates() -> None:
    project = Project(name="Projekt północ")
    site_id = uuid4()

    updated = project.with_site(site_id).with_site(site_id)

    assert updated.site_ids == (site_id,)
    assert project.site_ids == ()


def test_project_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="name"):
        Project(name=" ")
