"""Integration tests for the job queue and worker (Step 3 of
docs/WEB_ARCHITECTURE.md).

Requires Docker (an ephemeral PostGIS container via testcontainers), same as
``tests/test_postgres_repositories.py`` — skipped there, skipped here.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.postgres
psycopg = pytest.importorskip("psycopg")
pytest.importorskip("testcontainers")

from renewable_planner.adapters.geospatial.file_screening import (  # noqa: E402
    build_project,
    load_site,
)
from renewable_planner.adapters.postgres import (  # noqa: E402
    PostgresAnalysisRunRepository,
    PostgresJobRepository,
    PostgresProjectRepository,
    PostgresScreeningResultRepository,
)
from renewable_planner.adapters.postgres.schema import SCHEMA_SQL  # noqa: E402
from renewable_planner.worker import run_worker  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def dsn() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    try:
        container = PostgresContainer("postgis/postgis:16-3.4")
        container.start()
    except Exception as error:  # pragma: no cover - environment-dependent
        pytest.skip(f"Docker/PostGIS container unavailable: {error}")

    try:
        url = container.get_connection_url(driver=None)
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        yield url
    finally:
        container.stop()


@pytest.fixture
def repositories(
    dsn: str,
) -> tuple[
    PostgresJobRepository,
    PostgresProjectRepository,
    PostgresAnalysisRunRepository,
    PostgresScreeningResultRepository,
]:
    jobs = PostgresJobRepository(dsn)
    projects = PostgresProjectRepository(dsn)
    runs = PostgresAnalysisRunRepository(dsn)
    results = PostgresScreeningResultRepository(dsn, runs)
    return jobs, projects, runs, results


def _enqueue_screening_job(
    tmp_path: Path,
    jobs: PostgresJobRepository,
    projects: PostgresProjectRepository,
    *,
    rules_text: str | None = None,
) -> tuple[UUID, UUID, UUID]:
    site_path = tmp_path / "site.geojson"
    constraints_path = tmp_path / "constraints.geojson"
    rules_path = tmp_path / "rules.yaml"
    site_path.write_bytes((FIXTURES / "cli_site.geojson").read_bytes())
    constraints_path.write_bytes((FIXTURES / "cli_constraints.geojson").read_bytes())
    rules_path.write_text(
        rules_text or (FIXTURES / "cli_rules.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    site = load_site(site_path)
    project = build_project(site, site_path)
    projects.add(project)

    job_id = uuid4()
    jobs.enqueue(
        job_id,
        "screening",
        {
            "site_path": str(site_path),
            "constraints_path": str(constraints_path),
            "rules_path": str(rules_path),
            "project_id": str(project.id),
            "site_id": str(site.id),
            "technology": "wind",
            "country": "PL",
            "analysis_date": "2026-08-17",
        },
    )
    return job_id, project.id, site.id


def test_worker_completes_a_queued_job(
    dsn: str,
    tmp_path: Path,
    repositories: tuple[
        PostgresJobRepository,
        PostgresProjectRepository,
        PostgresAnalysisRunRepository,
        PostgresScreeningResultRepository,
    ],
) -> None:
    jobs, projects, runs, results = repositories
    job_id, _, _ = _enqueue_screening_job(tmp_path, jobs, projects)

    run_worker(dsn, max_iterations=1, poll_interval=0.0)

    job = jobs.get(job_id)
    assert job is not None
    assert job.status == "done"
    assert job.analysis_run_id is not None

    run = runs.get(job.analysis_run_id)
    assert run is not None
    assert run.status.value == "completed"

    result = results.get(job.analysis_run_id)
    assert result is not None
    assert result.spatial_result.initial_area_square_meters == pytest.approx(400.0)


def test_worker_retries_then_gives_up_after_max_attempts(
    dsn: str,
    tmp_path: Path,
    repositories: tuple[
        PostgresJobRepository,
        PostgresProjectRepository,
        PostgresAnalysisRunRepository,
        PostgresScreeningResultRepository,
    ],
) -> None:
    jobs, projects, runs, _results = repositories
    broken_rules = """
rules:
  - id: 20000000-0000-0000-0000-000000000099
    name: Zepsuta reguła
    severity: exclusion
    applies_to: [wind]
    source_layer: nonexistent_layer
    operation: intersects
    distance_m: 0
    legal_basis: synthetic-rules-v1
    valid_from: "2026-01-01"
"""
    job_id, _, _ = _enqueue_screening_job(tmp_path, jobs, projects, rules_text=broken_rules)

    run_worker(dsn, max_iterations=1, max_attempts=2, poll_interval=0.0)
    job = jobs.get(job_id)
    assert job is not None
    assert job.status == "queued"
    assert job.attempts == 1
    assert job.last_error

    run_worker(dsn, max_iterations=1, max_attempts=2, poll_interval=0.0)
    job = jobs.get(job_id)
    assert job is not None
    assert job.status == "failed"
    assert job.attempts == 2

    assert job.analysis_run_id is not None
    failed_run = runs.get(job.analysis_run_id)
    assert failed_run is not None
    assert failed_run.status.value == "failed"


def test_claim_next_does_not_return_the_same_job_twice(
    dsn: str,
    tmp_path: Path,
    repositories: tuple[
        PostgresJobRepository,
        PostgresProjectRepository,
        PostgresAnalysisRunRepository,
        PostgresScreeningResultRepository,
    ],
) -> None:
    jobs, projects, _runs, _results = repositories
    _enqueue_screening_job(tmp_path, jobs, projects)

    first = jobs.claim_next("worker-a")
    second = jobs.claim_next("worker-b")

    assert first is not None
    assert second is None


def test_job_repository_get_returns_none_for_unknown_id(dsn: str) -> None:
    jobs = PostgresJobRepository(dsn)
    assert jobs.get(uuid4()) is None


def test_job_repository_lists_recent_jobs_of_one_type_newest_first(dsn: str) -> None:
    jobs = PostgresJobRepository(dsn)
    first = jobs.enqueue(uuid4(), "listing-test", {"n": 1})
    second = jobs.enqueue(uuid4(), "listing-test", {"n": 2})
    jobs.enqueue(uuid4(), "other-type", {"n": 3})

    recent = jobs.list_recent("listing-test", 10)

    assert [job.id for job in recent] == [second.id, first.id]
