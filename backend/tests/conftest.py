"""Shared fixtures.

Integration tests run against a schema created by the real Alembic migrations, on
SQLite always and additionally on PostgreSQL when TEST_DATABASE_URL is set, e.g.

    TEST_DATABASE_URL=postgresql+psycopg://agentforge:agentforge@127.0.0.1:5432/agentforge_test
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.application.auth import AuthenticationError
from app.domain.user import User
from app.infrastructure.config import Settings
from app.infrastructure.persistence.orm import Base
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]

USER_A = User(id=uuid.UUID("00000000-0000-4000-8000-00000000000a"), email="a@example.com", name="Ada")
USER_B = User(id=uuid.UUID("00000000-0000-4000-8000-00000000000b"), email="b@example.com", name="Bob")


class FakeTokenVerifier:
    """Maps opaque test tokens to users; real JWT verification is unit-tested separately."""

    def __init__(self, users: dict[str, User]) -> None:
        self.users = users

    def verify(self, token: str) -> User:
        try:
            return self.users[token]
        except KeyError:
            raise AuthenticationError("Invalid access token") from None


TOKENS = {"token-a": USER_A, "token-b": USER_B}


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_settings(database_url: str, **overrides) -> Settings:
    defaults = {
        "database_url": database_url,
        "environment": "test",
        "llm_provider": None,
        "llm_model": None,
        "llm_api_key": None,
        "log_level": "WARNING",
    }
    # _env_file=None: tests must not pick up a developer's local .env.
    return Settings(_env_file=None, **{**defaults, **overrides})


def run_migrations(database_url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.attributes["settings"] = make_settings(database_url)
    command.upgrade(config, "head")


def _backends() -> list:
    params = [pytest.param("sqlite", id="sqlite")]
    if os.environ.get("TEST_DATABASE_URL"):
        params.append(pytest.param("postgres", id="postgres", marks=pytest.mark.postgres))
    return params


@pytest.fixture(scope="session", params=_backends())
def migrated_database_url(request, tmp_path_factory) -> str:
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path_factory.mktemp('db') / 'agentforge-test.db'}"
    else:
        url = os.environ["TEST_DATABASE_URL"]
    run_migrations(url)
    return url


@pytest.fixture
def fake_llm():
    """No LLM by default; modules that run workflows override this fixture."""
    return None


@pytest.fixture
def fake_sandbox():
    from tests.fakes import FakeSandbox

    return FakeSandbox()


@pytest.fixture
def app(migrated_database_url, fake_llm, fake_sandbox):
    application = create_app(
        make_settings(migrated_database_url),
        token_verifier=FakeTokenVerifier(TOKENS),
        llm=fake_llm,
        sandbox=fake_sandbox,
        run_workers=False,  # tests drive the queue explicitly with drain()
    )
    yield application
    # Leave every test with empty tables.
    with application.state.engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    """Signed in as USER_A."""
    with TestClient(app, headers=auth_headers("token-a")) as test_client:
        yield test_client


@pytest.fixture
def client_b(app) -> Iterator[TestClient]:
    """Signed in as USER_B."""
    with TestClient(app, headers=auth_headers("token-b")) as test_client:
        yield test_client


@pytest.fixture
def anonymous_client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(app) -> Iterator[Session]:
    session: Session = app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def project_payload() -> dict:
    return {
        "name": "Student Management API",
        "requirements": "Build a student management REST API with registration and attendance.",
        "language": "python",
        "framework": "FastAPI",
        "database_preference": "PostgreSQL",
    }


def drain(application, max_runs: int = 20) -> int:
    """Process queued runs synchronously, exactly as a worker would."""
    from app.infrastructure.worker.background import BackgroundWorker

    container = application.state.container
    worker = BackgroundWorker(session_factory=container.session_factory, engine_factory=container.ensure_engine)
    processed = 0
    while processed < max_runs and worker.run_once("test-worker"):
        processed += 1
    return processed
