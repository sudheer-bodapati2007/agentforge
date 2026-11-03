"""End-to-end validation of the required workflow scenarios against the REAL Docker
sandbox, through the HTTP API, the job queue, the worker and the checkpointer.

Model output is scripted (deterministic) so each scenario is reproducible; everything
else is real: pytest runs in the isolated container, ruff runs the security rules, and
routing decisions follow the actual results.

    1. passes on the first test run
    2. fails initially, the debugging agent fixes it, the re-run passes
    3. keeps failing until the retry limit and stops safely as partially completed
    4. requires human approval (plan), then completes after approval
    5. a tool-verified security finding triggers an approved correction cycle
    6. a project with a PostgreSQL database: schema step, migrations applied to a real
       throwaway database, tests against it, schema read back and stored
"""

import subprocess

import pytest

from app.application.agents.schemas import CodeChangeSet, DebugPatch, FileContent, SchemaDesign, TablePlan, TestSuite
from app.infrastructure.llm import scripted
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox
from tests.conftest import drain
from tests.fakes import ScenarioLLM

pytestmark = pytest.mark.docker

SANDBOX = DockerSandbox(image="agentforge-sandbox-python:2", timeout_seconds=120)
if not SANDBOX.status().available:
    pytest.skip(f"sandbox unavailable: {SANDBOX.status().detail}", allow_module_level=True)


def source(op: str, extra: dict[str, str] | None = None) -> CodeChangeSet:
    files = {
        "app/__init__.py": "",
        "app/models.py": scripted.MODELS_PY,
        "app/store.py": scripted.STORE_PY_TEMPLATE.format(op=op),
        "app/main.py": scripted.MAIN_PY,
        **(extra or {}),
    }
    return CodeChangeSet(files=[FileContent(path=p, content=c) for p, c in files.items()])


UNSAFE_HELPER = "import subprocess\n\n\ndef run(command: str) -> int:\n    return subprocess.call(command, shell=True)\n"
SAFE_HELPER = "import subprocess\n\n\ndef run(args: list[str]) -> int:\n    return subprocess.call(args)\n"


@pytest.fixture
def fake_llm():
    return ScenarioLLM()


@pytest.fixture
def fake_sandbox():
    return SANDBOX


@pytest.fixture
def project_id(client, project_payload):
    # Scenarios 1-5 are about the workflow, not databases (scenario 6 covers PostgreSQL).
    return client.post("/api/projects", json={**project_payload, "database_preference": None}).json()["id"]


def run_to_end(app, client, project_id, require_approval=False):
    run_id = client.post(f"/api/projects/{project_id}/runs", json={"require_approval": require_approval}).json()["id"]
    drain(app)
    return run_id


def summary(client, run_id):
    run = client.get(f"/api/runs/{run_id}").json()
    tests = client.get(f"/api/runs/{run_id}/tests").json()
    return run, [(t["passed"], t["total"]) for t in tests]


def test_1_passes_first_time(app, client, project_id, fake_llm):
    fake_llm.overrides["coder"] = source("==")
    run, attempts = summary(client, run_to_end(app, client, project_id))
    assert run["status"] == "completed"
    assert attempts == [(6, 6)]
    assert run["debug_iterations"] == 0


def test_2_fails_then_is_fixed_by_the_debugger(app, client, project_id):
    run, attempts = summary(client, run_to_end(app, client, project_id))  # scripted bug
    assert attempts == [(5, 6), (6, 6)]
    assert run["debug_iterations"] == 1
    assert run["status"] == "completed"


def test_3_stops_at_the_retry_limit(app, client, project_id, fake_llm):
    fake_llm.overrides["debugger"] = DebugPatch(
        diagnosis="(scripted) ineffective fix", root_causes=["unknown"], files=[FileContent(path="app/store.py", content=scripted.STORE_PY_TEMPLATE.format(op="!="))]
    )
    run, attempts = summary(client, run_to_end(app, client, project_id))
    assert run["status"] == "partially_completed"
    assert run["debug_iterations"] == run["max_debug_iterations"] == 3
    assert attempts == [(5, 6)] * 4
    assert any("failed" in item for item in run["final_report"]["limitations"])


def test_4_requires_and_honours_human_approval(app, client, project_id):
    run_id = run_to_end(app, client, project_id, require_approval=True)
    run, attempts = summary(client, run_id)
    assert run["status"] == "awaiting_approval" and attempts == []
    approval = client.get(f"/api/runs/{run_id}/approvals").json()[0]
    client.post(f"/api/runs/{run_id}/approvals/{approval['id']}", json={"approve": True})
    drain(app)
    run, attempts = summary(client, run_id)
    assert run["status"] == "completed"
    assert attempts[-1] == (6, 6)


def test_5_security_finding_triggers_approved_correction(app, client, project_id, fake_llm):
    fake_llm.overrides["coder"] = source("==", {"app/shell.py": UNSAFE_HELPER})
    fake_llm.overrides["corrector"] = CodeChangeSet(files=[FileContent(path="app/shell.py", content=SAFE_HELPER)])
    run_id = run_to_end(app, client, project_id, require_approval=True)

    # Plan approval first.
    plan = client.get(f"/api/runs/{run_id}/approvals").json()[0]
    client.post(f"/api/runs/{run_id}/approvals/{plan['id']}", json={"approve": True})
    drain(app)

    # ruff (a deterministic tool, not the LLM) found shell=True: approval to fix is requested.
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "awaiting_approval"
    pending = [a for a in client.get(f"/api/runs/{run_id}/approvals").json() if a["status"] == "pending"][0]
    assert pending["kind"] == "corrections"
    assert "app/shell.py" in pending["affected_resources"]
    first_review = client.get(f"/api/runs/{run_id}/reviews").json()
    assert any(f["source"] == "tool" and f["title"].startswith("S602") for f in first_review)

    client.post(f"/api/runs/{run_id}/approvals/{pending['id']}", json={"approve": True})
    drain(app)
    run, attempts = summary(client, run_id)
    assert run["status"] == "completed"
    assert len(attempts) == 2  # re-tested after the correction
    findings = client.get(f"/api/runs/{run_id}/reviews").json()
    latest = max(f["cycle"] for f in findings)
    assert not any(f["title"].startswith("S602") for f in findings if f["cycle"] == latest)


# --- 6. a project with a PostgreSQL database ------------------------------------------

LIBRARY_SCHEMA = SchemaDesign(
    summary="Authors and books, each book written by one author.",
    tables=[TablePlan(name="authors", purpose="A writer"), TablePlan(name="books", purpose="A book")],
    migration_sql=(
        "CREATE TABLE authors (id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE);\n"
        "CREATE TABLE books (\n"
        "    id SERIAL PRIMARY KEY,\n"
        "    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,\n"
        "    title TEXT NOT NULL\n"
        ");\n"
        "CREATE INDEX ix_books_author_id ON books(author_id);"
    ),
)
LIBRARY_APP = (
    "import os\n"
    "from sqlalchemy import create_engine, text\n\n"
    "engine = create_engine(os.environ['DATABASE_URL'])\n\n\n"
    "def add_book(author: str, title: str) -> int:\n"
    "    with engine.begin() as conn:\n"
    "        author_id = conn.execute(text('INSERT INTO authors (name) VALUES (:n) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id'), {'n': author}).scalar_one()\n"
    "        return conn.execute(text('INSERT INTO books (author_id, title) VALUES (:a, :t) RETURNING id'), {'a': author_id, 't': title}).scalar_one()\n\n\n"
    "def titles_by(author: str) -> list[str]:\n"
    "    with engine.connect() as conn:\n"
    "        rows = conn.execute(text('SELECT b.title FROM books b JOIN authors a ON a.id = b.author_id WHERE a.name = :n ORDER BY b.id'), {'n': author})\n"
    "        return [r.title for r in rows]\n"
)
LIBRARY_TESTS = (
    "import pytest\n"
    "from sqlalchemy import text\n"
    "from app.library import add_book, engine, titles_by\n\n\n"
    "@pytest.fixture(autouse=True)\n"
    "def clean():\n"
    "    with engine.begin() as conn:\n"
    "        conn.execute(text('TRUNCATE books, authors RESTART IDENTITY CASCADE'))\n\n\n"
    "def test_books_are_stored_per_author():\n"
    "    add_book('Le Guin', 'The Dispossessed')\n"
    "    add_book('Le Guin', 'The Lathe of Heaven')\n"
    "    add_book('Butler', 'Kindred')\n"
    "    assert titles_by('Le Guin') == ['The Dispossessed', 'The Lathe of Heaven']\n\n\n"
    "def test_unknown_author_has_no_books():\n"
    "    assert titles_by('Nobody') == []\n"
)


def test_6_database_project_migrates_and_tests_against_real_postgres(app, client, project_payload, fake_llm):
    if subprocess.run(["docker", "image", "inspect", "postgres:17-alpine"], capture_output=True).returncode != 0:
        pytest.skip("postgres:17-alpine is not pulled")
    fake_llm.overrides["schema"] = LIBRARY_SCHEMA
    fake_llm.overrides["coder"] = CodeChangeSet(
        files=[FileContent(path="app/__init__.py", content=""), FileContent(path="app/library.py", content=LIBRARY_APP)]
    )
    fake_llm.overrides["tester"] = TestSuite(files=[FileContent(path="tests/test_library.py", content=LIBRARY_TESTS)])
    project = client.post("/api/projects", json={**project_payload, "database_preference": "PostgreSQL"}).json()["id"]
    run_id = run_to_end(app, client, project)

    run, attempts = summary(client, run_id)
    assert run["status"] == "completed", run["error"]
    assert attempts == [(2, 2)]
    agents = [a["node"] for a in client.get(f"/api/runs/{run_id}/agents").json()]
    assert agents[:3] == ["plan", "architect", "schema"]
    database = client.get(f"/api/runs/{run_id}/tests").json()[0]["database"]
    assert [m["file"] for m in database["migrations"] if m["ok"]] == ["0001_initial.sql"]
    assert {t["name"] for t in database["schema"]} == {"authors", "books"}
    files = {a["path"] for a in client.get(f"/api/runs/{run_id}/artifacts").json()}
    assert "db/migrations/0001_initial.sql" in files
    assert run["final_report"]["verified"]["database"]["schema"]