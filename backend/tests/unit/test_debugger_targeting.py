"""The debugger is told where failures happen and which files it keeps changing for
nothing. Built from a real run where a 7B model edited app/repository.py three times while
every failure was raised in tests/test_repository.py (the tests called a generator directly)."""

from app.application.agents.prompts import DEBUGGER_SYSTEM, debugger_user, numbered
from app.application.agents.schemas import DebugPatch, FileContent
from app.application.workflow.failures import changed_paths, failure_locations, ineffective_files
from app.application.workflow.steps import strip_line_numbers
from app.domain.testing import TestCaseFailure, TestReport
from tests.fakes import FakeSandbox, ScenarioLLM, passing_report
from tests.unit.test_workflow_engine import Harness, initial

REPOSITORY = "def get_db():\n    db = Session()\n    try:\n        yield db\n    finally:\n        db.close()\n\n\ndef get_counter(db):\n    return db.execute('select 1')\n"
TESTS = "from app.repository import get_db, get_counter\n\n\ndef test_get_counter_initial_value():\n    db = get_db()\n    counter = get_counter(db)\n    assert counter == 0\n"
FILES = {"app/repository.py": REPOSITORY, "tests/test_repository.py": TESTS}

# The failure text pytest produced in the real run (shape of JUnit messages).
REAL_FAILURE = TestCaseFailure(
    name="tests.test_repository::test_get_counter_initial_value",
    message=(
        "AttributeError: 'SessionTransaction' object has no attribute 'execute'\n"
        "def test_get_counter_initial_value():\n    db = get_db()\n>   counter = get_counter(db)\n\n"
        "tests/test_repository.py:6: \n_ _ _\napp/repository.py:10: in get_counter\n    return db.execute('select 1')\n"
        "E   AttributeError: 'SessionTransaction' object has no attribute 'execute'"
    ),
    file_path="tests/test_repository.py",
    line=6,
)


def failing() -> TestReport:
    return TestReport(executed=True, command="pytest", exit_code=1, total=5, passed=0, failed=5, failures=[REAL_FAILURE] * 5)


def test_failure_locations_come_from_the_real_traceback_with_their_code():
    report = {"failures": [{"name": REAL_FAILURE.name, "message": REAL_FAILURE.message, "file_path": "tests/test_repository.py", "line": 6}]}
    locations = failure_locations(report, FILES)
    assert locations[0] == {"file": "tests/test_repository.py", "line": 6, "code": "counter = get_counter(db)", "occurrences": 2}
    assert {"file": "app/repository.py", "line": 10, "code": "return db.execute('select 1')", "occurrences": 1} in locations


def test_failure_locations_never_invent_lines():
    report = {"failures": [{"message": "tests/test_repository.py:999: boom\nother/x.py:3\napp/missing.py:1"}], "output_excerpt": ""}
    assert failure_locations(report, FILES) == []
    assert failure_locations({}, FILES) == []


def test_ineffective_files_count_only_attempts_that_changed_nothing():
    history = [
        {"iteration": 1, "files_changed": ["app/a.py"], "failure_signature": "A"},  # A -> B: it helped
        {"iteration": 2, "files_changed": ["app/repository.py"], "failure_signature": "B"},  # B -> B: no effect
        {"iteration": 3, "files_changed": ["app/repository.py"], "failure_signature": "B"},  # B -> B (current): no effect
    ]
    assert ineffective_files(history, "B") == {"app/repository.py": 2}
    assert ineffective_files([], "A") == {}


def test_a_rewrite_with_identical_content_is_not_a_change():
    assert changed_paths({"a": "x", "b": "y"}, {"a": "x", "b": "z"}, ["a", "b"]) == ["b"]


def test_the_debugger_sees_line_numbers_locations_and_a_named_stuck_file():
    prompt = debugger_user(
        "Build a counter",
        {},
        FILES,
        "",
        [],
        locations=[{"file": "tests/test_repository.py", "line": 6, "code": "counter = get_counter(db)", "occurrences": 5}],
        ineffective={"app/repository.py": 2},
    )
    assert "   6 | " in prompt and "counter = get_counter(db)" in prompt
    assert "tests/test_repository.py:6 (5x)  counter = get_counter(db)" in prompt
    assert "STUCK: you already changed app/repository.py (2x)" in prompt
    assert "The failures are reported in tests/test_repository.py" in prompt
    assert "uses the code incorrectly" in DEBUGGER_SYSTEM


def test_copied_line_numbers_are_stripped_but_real_code_is_untouched():
    copied = numbered("def f():\n    return 1\n")
    assert strip_line_numbers(copied) == "def f():\n    return 1\n"
    table = "rows = [\n  1 | 2,\n]\n"  # code that merely contains a "1 |" is left alone
    assert strip_line_numbers(table) == table
    assert strip_line_numbers("") == ""


def test_a_stuck_debugger_is_pointed_at_the_file_where_the_failures_happen():
    wrong_fix = DebugPatch(diagnosis="get_db is a generator", root_causes=["x"], files=[FileContent(path="app/repository.py", content=REPOSITORY + "\n# tweak\n")])
    wrong_again = DebugPatch(diagnosis="get_db is a generator", root_causes=["x"], files=[FileContent(path="app/repository.py", content=REPOSITORY + "\n# tweak 2\n")])
    h = Harness(llm=ScenarioLLM({"debugger": [wrong_fix, wrong_again]}), sandbox=FakeSandbox([failing()]))
    state = {**initial(max_debug=3), "files": dict(FILES)}
    h.llm.overrides["coder"] = None
    out = h.run(state)
    prompts = h.llm.prompts["debugger"]
    assert "STUCK" not in prompts[0]
    # Attempt 2 repeats the refuted diagnosis on the same file: rejected, and told where to look.
    assert "STUCK: you already changed app/repository.py (1x)" in prompts[1]
    assert "REJECTED: your proposed fix repeats attempt 1, which was measured as REFUTED" in prompts[2]
    assert "the failures are reported in tests/test_repository.py" in prompts[2]
    assert all("tests/test_repository.py:6" in p for p in prompts)
    assert out.state["outcome"] == "partially_completed"


def test_a_fix_that_changes_nothing_is_reported_as_such():
    # Whatever the coder wrote, the debugger "fixes" app/main.py with identical content.
    h = Harness(sandbox=FakeSandbox([failing(), passing_report()]))
    h.run(initial(max_debug=0))
    current = h.journal.files["app/main.py"]
    noop = DebugPatch(diagnosis="rewrote it", root_causes=[], files=[FileContent(path="app/main.py", content=current)])
    h2 = Harness(llm=ScenarioLLM({"debugger": [noop, noop]}), sandbox=FakeSandbox([failing()]))
    out = h2.run(initial(max_debug=2))
    patches = [e for e in h2.journal.events if e["type"] == "debug.patch"]
    assert patches[0]["no_change"] is True and patches[0]["files"] == []
    assert "no file was actually changed" in h2.llm.prompts["debugger"][1]
    assert out.state["debug_history"][0]["files_changed"] == []
