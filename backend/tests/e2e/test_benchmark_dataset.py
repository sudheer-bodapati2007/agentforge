"""The benchmark's measuring instrument, validated against the real Docker sandbox.

A benchmark is only as good as its reference tests, so before trusting any score:
  - every known-good solution must pass its task's hidden reference tests;
  - known-bad code (the planted bug, the unauthenticated app, plausible "improvements")
    must fail them;
  - the runner must grade a perfect system as 100% solved and a broken one as not solved.
"""

import re
from pathlib import Path

import pytest

from app.application.evaluation.benchmark import BenchmarkRunner
from app.application.evaluation.ports import Attempt
from app.domain.evaluation import EvaluationTask, SystemKind, TestTally, summarize
from app.infrastructure.evaluation.task_loader import load_tasks
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox

pytestmark = pytest.mark.docker

SANDBOX = DockerSandbox(image="agentforge-sandbox-python:2", timeout_seconds=90)
if not SANDBOX.status().available:
    pytest.skip(f"sandbox unavailable: {SANDBOX.status().detail}", allow_module_level=True)

DATASET = Path(__file__).resolve().parents[3] / "evals" / "datasets"
TASKS = {task.id: task for task in load_tasks(DATASET)}


def solution(task_id: str) -> dict[str, str]:
    root = DATASET / "solutions" / task_id
    files = {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*")
        if p.is_file() and p.suffix in (".py", ".sql")
    }
    return {"app/__init__.py": "", **files}


def prompt_code(task_id: str) -> str:
    """The code block embedded in a task prompt (the code the systems are given)."""
    return re.search(r"```python\n(.*?)```", TASKS[task_id].requirements, re.DOTALL).group(1)


def grade(task: EvaluationTask, files: dict[str, str]):
    return SANDBOX.run_tests({**files, **task.reference_tests}, database=task.database)


def test_dataset_has_seven_tasks_with_solutions():
    assert set(TASKS) == {"rest_api", "input_validation", "crud", "fix_bug", "write_tests", "add_auth", "db_schema"}
    assert [t.id for t in TASKS.values() if t.database] == ["db_schema"]
    for task_id in TASKS:
        assert (DATASET / "solutions" / task_id).is_dir(), f"no known-good solution for {task_id}"


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_known_good_solution_passes_every_reference_test(task_id):
    report = grade(TASKS[task_id], solution(task_id))
    assert report.executed, report.unavailable_reason
    assert report.succeeded, report.output_excerpt
    assert report.total >= 5


IMPROVED_SLUGIFY = '''
import re
import unicodedata


def slugify(text):
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
'''

REQUIRED_HEADER_AUTH = '''
import hmac, os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()
_notes = []


class NoteIn(BaseModel):
    text: str


def check(key):
    expected = os.environ.get("NOTES_API_KEY", "")
    if not expected or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=401)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/notes")
def list_notes(x_api_key: str = Header(...)):
    check(x_api_key)
    return _notes


@app.post("/notes", status_code=201)
def add_note(note: NoteIn, x_api_key: str = Header(...)):
    check(x_api_key)
    _notes.append({"id": len(_notes) + 1, "text": note.text})
    return _notes[-1]
'''


@pytest.mark.parametrize(
    "task_id, path, code, why",
    [
        ("fix_bug", "app/stats.py", lambda: prompt_code("fix_bug"), "the planted bug itself"),
        ("add_auth", "app/main.py", lambda: prompt_code("add_auth"), "the app without authentication"),
        ("add_auth", "app/main.py", lambda: REQUIRED_HEADER_AUTH, "a required header answers 422, not 401"),
        ("write_tests", "app/slug.py", lambda: IMPROVED_SLUGIFY, "an 'improved' slugify that changes behaviour"),
        (
            "input_validation",
            "app/validation.py",
            lambda: solution("input_validation")["app/validation.py"].replace(
                "if type(age) is not int or not 13", "age = int(age)\n    if not 13"
            ),
            "coercing the string '30' to an age",
        ),
        (
            "db_schema",
            "db/migrations/0001_initial.sql",
            lambda: solution("db_schema")["db/migrations/0001_initial.sql"].replace(" CHECK (year > 1400)", ""),
            "the year rule only in Python, not in the database",
        ),
        (
            "db_schema",
            "db/migrations/0001_initial.sql",
            lambda: solution("db_schema")["db/migrations/0001_initial.sql"].replace(" ON DELETE CASCADE", ""),
            "deleting an author does not cascade to their books",
        ),
    ],
)
def test_known_bad_code_fails_the_reference_tests(task_id, path, code, why):
    base = solution(task_id) if task_id == "db_schema" else {"app/__init__.py": ""}  # the bad part replaces one file
    report = grade(TASKS[task_id], {**base, path: code()})
    assert report.executed
    assert not report.succeeded, f"reference tests did not catch: {why}"


class OracleSystem:
    """Returns the known-good solution: the ceiling the benchmark must report as 100%."""

    kind = SystemKind.MULTI_AGENT

    def solve(self, task):
        return Attempt(files=solution(task.id), own_tests=TestTally(executed=False))


class CrashingSystem:
    kind = SystemKind.SINGLE_AGENT

    def solve(self, task):
        raise ValueError("model returned invalid JSON")


def test_runner_grades_a_perfect_and_a_crashing_system():
    tasks = [TASKS["fix_bug"], TASKS["crud"]]
    runner = BenchmarkRunner(sandbox=SANDBOX, repository=None, model_name="oracle", demo_model=False)
    results = runner.run("bench-oracle", tasks, [OracleSystem(), CrashingSystem()])

    oracle, crashing = summarize(results)
    assert (oracle.system, oracle.solved, oracle.solve_rate, oracle.reference_pass_rate) == (SystemKind.MULTI_AGENT, 2, 1.0, 1.0)
    assert (crashing.solved, crashing.solve_rate, crashing.reference_pass_rate, crashing.errors) == (0, 0.0, 0.0, 2)
    assert all(r.reference_tests.executed for r in results), "crashed attempts are still graded, as zero"
