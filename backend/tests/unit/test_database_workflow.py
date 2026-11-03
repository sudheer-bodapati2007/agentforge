"""Projects with a PostgreSQL database through the real LangGraph engine (fake model and
sandbox): the schema step, the database environment in prompts, migrations in the
sandbox call, and how migration failures reach the debugger and the outcome."""

from dataclasses import replace

from app.application.agents.prompts import DATABASE_ENVIRONMENT
from app.application.agents.schemas import CodeChangeSet, FileContent, SchemaDesign, TablePlan
from app.application.workflow.routing import wants_database
from app.application.workflow.steps import INITIAL_MIGRATION, application_files, migration_errors
from app.domain.testing import DatabaseReport, MigrationResult
from tests.fakes import FakeSandbox, ScenarioLLM, failing_report, passing_report
from tests.unit.test_workflow_engine import Harness, initial

SCHEMA = SchemaDesign(
    summary="Authors and their books.",
    tables=[TablePlan(name="authors", purpose="A writer"), TablePlan(name="books", purpose="A book by one author")],
    migration_sql="CREATE TABLE authors (id SERIAL PRIMARY KEY, name TEXT NOT NULL);",
)
MIGRATED = DatabaseReport(migrations=[MigrationResult("0001_initial.sql", True)], schema=[{"name": "authors", "columns": []}])
BROKEN = DatabaseReport(migrations=[MigrationResult("0001_initial.sql", False, 'relation "missing" does not exist')])


def database_state(**changes):
    return {**initial(), "database": True, "preferences": {"language": "python", "database": "PostgreSQL"}, **changes}


def test_postgres_preference_turns_the_database_on():
    assert wants_database({"database": "PostgreSQL"}) and wants_database({"database": "postgres 17"})
    assert not wants_database({"database": "MySQL"}) and not wants_database({"database": None}) and not wants_database(None)


def test_database_projects_design_a_schema_and_test_against_a_real_database():
    h = Harness(llm=ScenarioLLM({"schema": SCHEMA}), sandbox=FakeSandbox([replace(passing_report(), database=MIGRATED)]))
    out = h.run(database_state())
    assert out.state["outcome"] == "completed"
    assert h.journal.finished_nodes()[:4] == ["plan", "architect", "schema", "code"]
    assert h.journal.files[INITIAL_MIGRATION].startswith("CREATE TABLE authors")
    assert h.sandbox.database_calls == [True]
    for agent in ("planner", "architect", "schema", "coder", "tester"):
        assert DATABASE_ENVIRONMENT in h.llm.prompts[agent][0], agent
    assert "CREATE TABLE authors" in h.llm.prompts["coder"][0], "the coder sees the schema it must use"
    assert out.state["report"]["verified"]["database"]["schema"][0]["name"] == "authors"
    readme = h.journal.files["README.md"]
    assert "Database: PostgreSQL 17, 1 migration(s) applied; tables: authors" in readme


def test_projects_without_a_database_skip_the_schema_step():
    h = Harness()
    h.run()
    assert "schema" not in h.journal.finished_nodes()
    assert h.sandbox.database_calls == [False]
    assert DATABASE_ENVIRONMENT not in h.llm.prompts["coder"][0]


def test_a_failed_migration_is_not_success_and_the_debugger_sees_the_sql_error():
    broken = replace(passing_report(), database=BROKEN)  # even with every test passing
    fixed = replace(passing_report(), database=MIGRATED)
    h = Harness(llm=ScenarioLLM({"schema": SCHEMA}), sandbox=FakeSandbox([broken, fixed]))
    out = h.run(database_state())
    assert out.state["debug_iterations"] == 1
    prompt = h.llm.prompts["debugger"][0]
    assert "Database migrations FAILED" in prompt and 'relation \\"missing\\" does not exist' in prompt
    assert out.state["outcome"] == "completed"


def test_migrations_failing_until_the_limit_end_partially_completed_with_a_limitation():
    h = Harness(llm=ScenarioLLM({"schema": SCHEMA}), sandbox=FakeSandbox([replace(passing_report(), database=BROKEN)]))
    out = h.run(database_state(max_debug_iterations=1))
    assert out.state["outcome"] == "partially_completed"
    assert any("migrations did not apply" in item for item in out.state["report"]["limitations"])
    assert "MIGRATION FAILED" in h.journal.files["README.md"]


def test_the_coder_cannot_rewrite_the_schema_but_the_debugger_can_fix_it():
    assert not application_files("db/migrations/0001_initial.sql", {})
    assert application_files("app/models.py", {})
    sneaky = CodeChangeSet(
        files=[
            FileContent(path="app/main.py", content="x = 1\n"),
            FileContent(path="db/migrations/0001_initial.sql", content="DROP TABLE authors;"),
        ]
    )
    h = Harness(llm=ScenarioLLM({"schema": SCHEMA, "coder": sneaky}), sandbox=FakeSandbox([replace(failing_report(), database=MIGRATED)]))
    h.run(database_state(max_debug_iterations=0))
    assert h.journal.files[INITIAL_MIGRATION].startswith("CREATE TABLE authors")
    rejected = [e for e in h.journal.events if e["type"] == "files.rejected"]
    assert rejected and "db/migrations/0001_initial.sql" in rejected[0]["files"][0]


def test_migration_errors_include_runner_failures():
    report = {"database": {"migrations": [{"file": "a.sql", "ok": True}], "error": "OperationalError: could not connect"}}
    assert migration_errors(report) == [{"file": None, "error": "OperationalError: could not connect"}]
    assert migration_errors({}) == [] and migration_errors({"database": None}) == []


def test_the_report_only_counts_as_success_when_migrations_applied():
    assert replace(passing_report(), database=MIGRATED).succeeded
    assert not replace(passing_report(), database=BROKEN).succeeded
    assert not replace(passing_report(), database=DatabaseReport(error="runner crashed")).succeeded
    assert passing_report().succeeded  # projects without a database are unaffected
