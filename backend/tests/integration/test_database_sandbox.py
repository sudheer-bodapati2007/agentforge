"""Projects with a database, against the real Docker sandbox and a real throwaway PostgreSQL.

Skipped when Docker, the sandbox image or the database image is unavailable
(docker build -t agentforge-sandbox-python:2 docker/sandbox; docker pull postgres:17-alpine).
"""

import subprocess
import time

import pytest

from app.infrastructure.sandbox.docker_sandbox import CREATED_LABEL, LABEL, DockerSandbox

pytestmark = pytest.mark.docker

SANDBOX = DockerSandbox(image="agentforge-sandbox-python:2", timeout_seconds=120)
if not SANDBOX.status().available:
    pytest.skip(f"sandbox unavailable: {SANDBOX.status().detail}", allow_module_level=True)
if subprocess.run(["docker", "image", "inspect", "postgres:17-alpine"], capture_output=True).returncode != 0:
    pytest.skip("postgres:17-alpine is not pulled", allow_module_level=True)

MIGRATION = """
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    published INTEGER CHECK (published > 1400)
);
CREATE INDEX ix_books_author_id ON books(author_id);
"""

APP = '''
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])


def add_author(name):
    with engine.begin() as conn:
        return conn.execute(text("INSERT INTO authors (name) VALUES (:n) RETURNING id"), {"n": name}).scalar_one()


def add_book(author_id, title, published):
    with engine.begin() as conn:
        return conn.execute(
            text("INSERT INTO books (author_id, title, published) VALUES (:a, :t, :p) RETURNING id"),
            {"a": author_id, "t": title, "p": published},
        ).scalar_one()


def books_by(author_id):
    with engine.connect() as conn:
        return [r.title for r in conn.execute(text("SELECT title FROM books WHERE author_id = :a ORDER BY id"), {"a": author_id})]
'''

TESTS = '''
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.library import add_author, add_book, books_by, engine


@pytest.fixture(autouse=True)
def clean():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE books, authors RESTART IDENTITY CASCADE"))


def test_round_trip():
    author = add_author("Le Guin")
    add_book(author, "The Dispossessed", 1974)
    assert books_by(author) == ["The Dispossessed"]


def test_foreign_key_is_enforced():
    with pytest.raises(IntegrityError):
        add_book(999, "Orphan", 2000)


def test_check_constraint_is_enforced():
    author = add_author("Anon")
    with pytest.raises(IntegrityError):
        add_book(author, "Too old", 1000)
'''


def project(migration: str = MIGRATION, tests: str = TESTS) -> dict[str, str]:
    return {
        "app/__init__.py": "",
        "app/library.py": APP,
        "db/migrations/0001_initial.sql": migration,
        "tests/test_library.py": tests,
    }


def test_migrations_apply_tests_use_the_real_database_and_the_schema_is_reported():
    report = SANDBOX.run_tests(project(), database=True)
    assert report.executed, report.unavailable_reason
    assert report.succeeded, report.output_excerpt
    assert report.total == 3
    db = report.database
    assert db.migrated and [m.file for m in db.migrations] == ["0001_initial.sql"]
    tables = {t["name"]: t for t in db.schema}
    assert set(tables) == {"authors", "books"}
    books = tables["books"]
    assert {c["name"] for c in books["columns"]} == {"id", "author_id", "title", "published"}
    assert next(c for c in books["columns"] if c["name"] == "id")["primary_key"] is True
    assert books["foreign_keys"] == [{"columns": ["author_id"], "references": "authors(id)"}]
    assert any(i["name"] == "ix_books_author_id" for i in books["indexes"])
    assert tables["authors"]["unique"] == [["name"]]


def test_a_broken_migration_is_reported_and_blocks_success():
    report = SANDBOX.run_tests(project(migration=MIGRATION.replace("REFERENCES authors(id)", "REFERENCES missing(id)")), database=True)
    assert report.executed
    assert not report.database.migrated
    assert report.database.migrations[0].ok is False and "missing" in report.database.migrations[0].error
    assert not report.succeeded


PROBES = '''
import os, socket
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])


def test_no_internet():
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2)
    except OSError:
        return
    raise AssertionError("the internet is reachable from a database run")


def test_app_role_is_not_a_superuser():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar_one() is False


def test_sql_cannot_run_shell_commands():
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE probe (x TEXT)"))
        try:
            conn.execute(text("COPY probe FROM PROGRAM 'id'"))
        except Exception:
            return
    raise AssertionError("COPY ... PROGRAM ran a shell command")
'''


def test_database_runs_are_isolated():
    report = SANDBOX.run_tests(project(tests=PROBES), database=True)
    assert report.succeeded, report.output_excerpt


def mine(name: str) -> list[str]:
    """Containers and networks of one known run (other processes may be using the sandbox)."""
    containers = subprocess.run(["docker", "ps", "-aq", "--filter", f"name={name}"], capture_output=True, text=True).stdout.split()
    networks = subprocess.run(["docker", "network", "ls", "-q", "--filter", f"name={name}"], capture_output=True, text=True).stdout.split()
    return containers + networks


def known_run_name(monkeypatch) -> str:
    import uuid

    fixed = uuid.UUID("00000000-0000-4000-8000-00000000abcd")
    monkeypatch.setattr("app.infrastructure.sandbox.docker_sandbox.uuid.uuid4", lambda: fixed)
    return f"agentforge-test-{fixed.hex[:12]}"


def test_nothing_is_left_behind(monkeypatch):
    name = known_run_name(monkeypatch)
    assert SANDBOX.run_tests(project(), database=True).succeeded
    assert mine(name) == []


def test_cleanup_removes_abandoned_resources_but_never_ones_in_use():
    def network(name: str, created: int) -> None:
        subprocess.run(
            ["docker", "network", "create", "--internal", "--label", LABEL, "--label", f"{CREATED_LABEL}={created}", name],
            capture_output=True,
        )

    def exists(name: str) -> bool:
        return subprocess.run(["docker", "network", "inspect", name], capture_output=True).returncode == 0

    now = int(time.time())
    network("agentforge-test-abandoned-net", now - 24 * 3600)
    network("agentforge-test-in-use-net", now)
    try:
        assert SANDBOX.remove_leftovers() >= 1
        assert not exists("agentforge-test-abandoned-net")
        assert exists("agentforge-test-in-use-net"), "a resource another run may be using was removed"
    finally:
        subprocess.run(["docker", "network", "rm", "agentforge-test-abandoned-net", "agentforge-test-in-use-net"], capture_output=True)


def test_a_migration_that_never_finishes_is_stopped_and_cleaned_up(monkeypatch):
    quick = DockerSandbox(image="agentforge-sandbox-python:2", timeout_seconds=20)
    name = known_run_name(monkeypatch)
    report = quick.run_tests(project(migration="SELECT pg_sleep(600);"), database=True)
    assert report.executed and not report.succeeded
    assert "timeout" in report.output_excerpt.lower()
    assert mine(name) == []


def test_projects_without_migrations_still_run():
    files = {"app/__init__.py": "", "tests/test_x.py": "def test_ok():\n    assert True\n"}
    report = SANDBOX.run_tests(files, database=True)
    assert report.succeeded and report.database.migrations == [] and report.database.schema == []
