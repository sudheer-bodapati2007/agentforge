# Execution sandbox for generated Python projects.
# Runs with: no network, read-only root filesystem, read-only workspace mount, dropped
# capabilities, no-new-privileges, CPU/memory/PID limits and a wall-clock timeout
# (see app/infrastructure/sandbox/docker_sandbox.py). Packages must be preinstalled
# because the container has no network; keep this list in sync with
# app/application/agents/prompts.py::SANDBOX_PACKAGES.
#
# Projects with a database: the container joins a private network (no internet) with a
# throwaway PostgreSQL container, and run_database_tests.py applies the project's
# migrations and records the resulting schema before running pytest.
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install \
      pytest==9.1.1 \
      pytest-timeout==2.4.0 \
      fastapi==0.143.0 \
      httpx==0.28.1 \
      pydantic==2.14.1 \
      sqlalchemy==2.1.4 \
      psycopg[binary]==3.3.6 \
      ruff==0.17.0 \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox

COPY run_database_tests.py /opt/agentforge/run_database_tests.py

USER 10001:10001
WORKDIR /workspace
