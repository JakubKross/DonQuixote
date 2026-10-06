# Backend image (Step 5 of docs/WEB_ARCHITECTURE.md): one image, shared by
# the `api`, `worker` and `migrate` services in docker-compose.yml, which
# only differ in their `command:`. Avoids maintaining near-identical
# Dockerfiles for three processes that are the same codebase.
FROM python:3.12-slim

WORKDIR /app

# Copied explicitly (not `COPY . .`) so the frontend and local dev
# artifacts (.venv, node_modules, ...) never enter the build context's
# relevant layers, and so dependency installation is only invalidated by
# actual source changes.
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

# geopandas/shapely/pyproj/psycopg[binary] ship self-contained manylinux
# wheels (bundled GEOS/GDAL/PROJ/libpq) — no system packages needed here,
# consistent with CI (ubuntu-latest) installing the same extras without
# any apt step.
RUN pip install --no-cache-dir ".[web,postgres]"

EXPOSE 8000

# Default command runs the API; docker-compose.yml overrides `command:`
# for the `worker` and `migrate` services using this same image.
CMD ["uvicorn", "renewable_planner.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
