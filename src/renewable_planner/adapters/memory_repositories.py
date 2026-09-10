"""Process-shared in-memory repository adapters for the web API (Step 1).

Unlike ``adapters.geospatial.file_screening``'s ``MemoryAnalysisRunRepository``
and ``JsonResultRepository`` (throwaway, one-shot instances created fresh for
each CLI/Streamlit invocation), these are meant to be instantiated **once**
and shared across requests within one running API process, so a screening
run created by one request can be looked up by a later one.

This is explicitly a Step 1 stand-in (see docs/WEB_ARCHITECTURE.md): state is
lost on restart and not shared across worker processes. Step 2 replaces these
with PostGIS-backed adapters implementing the very same ports, with no change
to the API layer beyond composition wiring.
"""

import threading
from uuid import UUID

from renewable_planner.domain.analysis_run import AnalysisRun
from renewable_planner.domain.project import Project
from renewable_planner.domain.spatial_screening import ScreenSiteResult


class InMemoryProjectRepository:
    """Shared project store implementing ``ProjectRepository`` plus ``add``.

    ``add`` is not part of the ``ProjectRepository`` port — ``ScreenSite``
    never creates projects, only reads them — so it is a plain extra method
    the API composition layer uses directly.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._projects: dict[UUID, Project] = {}

    def add(self, project: Project) -> None:
        with self._lock:
            self._projects[project.id] = project

    def get(self, project_id: UUID) -> Project | None:
        with self._lock:
            return self._projects.get(project_id)


class InMemoryAnalysisRunRepository:
    """Keep the latest state of every analysis run, keyed by id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[UUID, AnalysisRun] = {}

    def save(self, analysis_run: AnalysisRun) -> None:
        with self._lock:
            self._runs[analysis_run.id] = analysis_run

    def get(self, analysis_run_id: UUID) -> AnalysisRun | None:
        with self._lock:
            return self._runs.get(analysis_run_id)


class InMemoryScreeningResultRepository:
    """Keep the screening result for every analysis run, keyed by run id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: dict[UUID, ScreenSiteResult] = {}

    def save(self, result: ScreenSiteResult) -> None:
        with self._lock:
            self._results[result.analysis_run.id] = result

    def get(self, analysis_run_id: UUID) -> ScreenSiteResult | None:
        with self._lock:
            return self._results.get(analysis_run_id)
