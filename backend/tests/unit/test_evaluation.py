"""Phase 6 benchmark: scoring rules, the two systems, the runner and the task loader."""

import itertools
import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.application.agents.schemas import CodeChangeSet, FileContent
from app.application.evaluation.benchmark import BenchmarkRunner
from app.application.evaluation.ports import Attempt
from app.application.evaluation.systems import EvaluationJournal, MultiAgentWorkflow, SingleAgentBaseline
from app.application.llm import Pricing, TokenUsage
from app.application.runs.ports import EngineOutcome
from app.application.workflow.ports import NullRetriever
from app.application.workflow.steps import WorkflowSteps
from app.bootstrap import build_benchmark
from app.domain.enums import FindingSeverity, FindingSource
from app.domain.errors import CapabilityUnavailableError, InvariantViolationError
from app.domain.evaluation import (
    EvaluationResult,
    EvaluationTask,
    SystemKind,
    TestTally,
    grading_files,
    summarize,
    validate_benchmark_id,
)
from app.domain.review import Finding
from app.domain.testing import TestReport
from app.infrastructure.evaluation.task_loader import load_tasks
from app.infrastructure.llm.scripted import ScriptedLLM
from app.infrastructure.workflow.langgraph_engine import LangGraphWorkflowEngine
from tests.conftest import make_settings
from tests.fakes import FakeSandbox, ScenarioLLM, failing_report, passing_report

DATASET = Path(__file__).resolve().parents[3] / "evals" / "datasets"
REFERENCE = {"tests/test_reference.py": "def test_ok():\n    assert True\n"}


def task(task_id="demo", **changes) -> EvaluationTask:
    values = {"id": task_id, "title": "Demo", "category": "CRUD", "requirements": "Build a thing.", "reference_tests": REFERENCE}
    return EvaluationTask(**{**values, **changes})


def result(system=SystemKind.MULTI_AGENT, *, ref=(5, 5), own=(3, 3), executed=True, cost=None, latency=10.0, debug=0, error=None):
    return EvaluationResult(
        benchmark_id="b1",
        task_id="demo",
        task_title="Demo",
        category="CRUD",
        system=system,
        model_name="m",
        demo_model=False,
        own_tests=TestTally(executed=executed, passed=own[0], total=own[1]),
        reference_tests=TestTally(executed=True, passed=ref[0], total=ref[1]),
        debug_iterations=debug,
        test_runs=1,
        findings_total=0,
        blocking_findings=0,
        latency_seconds=latency,
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=cost,
        human_interventions=0,
        error=error,
    )


# ---------------------------------------------------------------- domain rules


@pytest.mark.parametrize(
    "changes",
    [
        {"task_id": "Bad Id"},
        {"task_id": "../escape"},
        {"requirements": "   "},
        {"reference_tests": {}},
        {"reference_tests": {"app/test_x.py": "x"}},
        {"reference_tests": {"tests/../app/x.py": "x"}},
    ],
)
def test_invalid_tasks_are_rejected(changes):
    with pytest.raises(InvariantViolationError):
        task(**changes)


def test_tally_from_reports():
    assert TestTally.of(None) == TestTally(executed=False)
    assert TestTally.of(passing_report(4)).succeeded
    assert not TestTally.of(failing_report()).succeeded
    assert TestTally(executed=True, passed=0, total=0, errors=1).pass_fraction == 0.0  # import error = 0, not undefined
    assert TestTally(executed=False).pass_fraction is None
    assert not TestTally(executed=True, passed=3, total=3, errors=1).succeeded


def test_summary_rates():
    rows = [
        result(ref=(5, 5), latency=10, debug=2),
        result(ref=(1, 4), latency=30, debug=0),
        result(ref=(0, 0), latency=20, error="crashed", executed=False),
    ]
    (summary,) = summarize(rows)
    assert summary.tasks == 3 and summary.solved == 1
    assert summary.solve_rate == pytest.approx(1 / 3)
    # mean of per-task fractions: (1 + 0.25 + 0) / 3
    assert summary.reference_pass_rate == pytest.approx(1.25 / 3)
    assert summary.own_suite_success_rate == 1.0  # only suites that ran count
    assert summary.mean_debug_iterations == pytest.approx(2 / 3)
    assert summary.median_latency_seconds == 20
    assert summary.errors == 1
    assert summary.total_input_tokens == 300


def test_summary_cost_is_unknown_unless_every_row_is_priced():
    assert summarize([result(cost=0.01), result(cost=None)])[0].total_cost_usd is None
    assert summarize([result(cost=0.01), result(cost=0.02)])[0].total_cost_usd == pytest.approx(0.03)


def test_summary_is_per_system_in_fixed_order_and_empty_without_rows():
    rows = [result(SystemKind.SINGLE_AGENT), result(SystemKind.MULTI_AGENT)]
    assert [s.system for s in summarize(rows)] == [SystemKind.MULTI_AGENT, SystemKind.SINGLE_AGENT]
    assert summarize([]) == []


def test_own_suite_rate_is_undefined_when_no_suite_ran():
    assert summarize([result(executed=False)])[0].own_suite_success_rate is None


# ---------------------------------------------------------------- single-agent baseline


def baseline_answer(*files: tuple[str, str]) -> CodeChangeSet:
    return CodeChangeSet(files=[FileContent(path=p, content=c) for p, c in files])


def test_baseline_makes_one_call_and_runs_its_tests_once():
    llm = ScenarioLLM({"single_agent": baseline_answer(("app/stats.py", "x = 1\n"), ("tests/test_stats.py", "def test(): pass\n"))})
    sandbox = FakeSandbox([passing_report(2)])
    attempt = SingleAgentBaseline(llm=llm, sandbox=sandbox).solve(task(requirements="Fix the bug please."))
    assert llm.calls == ["single_agent"]
    assert "Fix the bug please." in llm.prompts["single_agent"][0]
    assert "<untrusted-requirements>" in llm.prompts["single_agent"][0]
    assert set(attempt.files) == {"app/__init__.py", "app/stats.py", "tests/test_stats.py"}
    assert attempt.own_tests == TestTally(executed=True, passed=2, total=2)
    assert (attempt.test_runs, attempt.debug_iterations) == (1, 0)
    assert attempt.usage == TokenUsage(100, 50)
    assert sandbox.test_calls == [attempt.files]


def test_baseline_drops_unsafe_paths_like_the_agents_do():
    llm = ScenarioLLM({"single_agent": baseline_answer(("app/ok.py", "x = 1\n"), ("../evil.py", "x"), ("/etc/passwd", "x"), ("run.sh", "x"))})
    attempt = SingleAgentBaseline(llm=llm, sandbox=FakeSandbox()).solve(task())
    assert set(attempt.files) == {"app/__init__.py", "app/ok.py"}


def test_baseline_without_source_files_fails():
    llm = ScenarioLLM({"single_agent": baseline_answer(("tests/test_only.py", "def test(): pass\n"))})
    with pytest.raises(InvariantViolationError):
        SingleAgentBaseline(llm=llm, sandbox=FakeSandbox()).solve(task())


# ---------------------------------------------------------------- multi-agent workflow


def multi_agent(sandbox, llm=None, max_debug=3):
    llm = llm or ScenarioLLM()
    journals = []

    def steps(run_id):
        journals.append(EvaluationJournal(run_id))
        return WorkflowSteps(llm=llm, sandbox=sandbox, journal=journals[-1], retriever=NullRetriever())

    engine = LangGraphWorkflowEngine(checkpointer=InMemorySaver(), steps_factory=steps)
    ids = (f"run-{n}" for n in itertools.count())
    return MultiAgentWorkflow(engine=engine, max_debug_iterations=max_debug, max_review_corrections=1, run_ids=lambda: next(ids)), journals


def test_multi_agent_runs_the_whole_graph_without_approvals():
    system, journals = multi_agent(FakeSandbox([failing_report(), passing_report(3)]))
    attempt = system.solve(task())
    assert attempt.own_tests == TestTally(executed=True, passed=3, total=3)
    assert (attempt.debug_iterations, attempt.test_runs) == (1, 2)
    assert "app/main.py" in attempt.files and "README.md" in attempt.files
    assert attempt.usage.input_tokens > 0
    assert attempt.human_interventions == 0
    nodes = [e["node"] for e in journals[0].events if e["type"] == "step.finished"]
    assert nodes[0] == "plan" and nodes[-1] == "report"


def test_multi_agent_uses_a_fresh_run_per_task():
    system, journals = multi_agent(FakeSandbox())
    system.solve(task("one"))
    system.solve(task("two"))
    assert [j.run_id for j in journals] == ["run-0", "run-1"]


def test_multi_agent_refuses_to_wait_for_a_human():
    class PausingEngine:
        def execute(self, run_id, state, resume):
            return EngineOutcome(interrupted=True, state={}, interrupt={"kind": "plan"})

    system = MultiAgentWorkflow(engine=PausingEngine(), max_debug_iterations=1, max_review_corrections=1)
    with pytest.raises(RuntimeError, match="human decision"):
        system.solve(task())


def test_evaluation_journal_never_creates_approvals():
    with pytest.raises(RuntimeError):
        EvaluationJournal("r").ensure_approval(kind="plan", cycle=1, reason="", affected_resources=[], security_notes=None, details={})


# ---------------------------------------------------------------- runner


class FixedSystem:
    def __init__(self, kind, attempt=None, error=None):
        self.kind = kind
        self.attempt = attempt
        self.error = error
        self.calls = 0

    def solve(self, _task):
        self.calls += 1
        if self.error:
            raise self.error
        return self.attempt


class RecordingRepository:
    def __init__(self):
        self.saved = []

    def save(self, result):
        self.saved.append(result)


def clock(*ticks):
    values = iter(ticks)
    return lambda: next(values)


def test_runner_grades_with_reference_tests_only():
    attempt = Attempt(
        files={"app/__init__.py": "", "app/x.py": "x = 1\n", "tests/test_mine.py": "def test(): assert False\n"},
        own_tests=TestTally(executed=True, passed=0, total=1),
        test_runs=1,
        usage=TokenUsage(1000, 500),
    )
    sandbox = FakeSandbox([passing_report(7)])
    repository = RecordingRepository()
    runner = BenchmarkRunner(
        sandbox=sandbox, repository=repository, model_name="m", demo_model=False, pricing=Pricing(1.0, 2.0), clock=clock(5.0, 17.5)
    )
    (row,) = runner.run("b1", [task()], [FixedSystem(SystemKind.SINGLE_AGENT, attempt)])

    graded = sandbox.test_calls[-1]
    assert "tests/test_mine.py" not in graded, "a system's own tests must not grade it"
    assert graded["tests/test_reference.py"] == REFERENCE["tests/test_reference.py"]
    assert graded["app/x.py"] == "x = 1\n"
    assert row.solved and row.reference_tests == TestTally(executed=True, passed=7, total=7)
    assert row.own_tests.passed == 0  # recorded as reported, separately
    assert row.latency_seconds == 12.5
    assert row.estimated_cost_usd == pytest.approx((1000 * 1.0 + 500 * 2.0) / 1_000_000)
    assert repository.saved == [row]


def test_runner_records_a_crash_as_an_unsolved_attempt():
    sandbox = FakeSandbox([failing_report(failed=1, total=1)])
    runner = BenchmarkRunner(sandbox=sandbox, repository=None, model_name="m", demo_model=False, clock=clock(0.0, 3.0))
    (row,) = runner.run("b1", [task()], [FixedSystem(SystemKind.SINGLE_AGENT, error=ValueError("invalid JSON from model"))])
    assert row.error == "invalid JSON from model"
    assert not row.solved
    assert row.estimated_cost_usd is None  # no pricing configured: unknown, not zero
    assert row.findings_total == 0
    assert sandbox.test_calls[-1] == REFERENCE  # still graded, against no code


def test_an_exhausted_quota_stops_the_benchmark_instead_of_failing_tasks():
    from app.application.llm import LLMUnavailableError

    repository = RecordingRepository()
    ok = FixedSystem(SystemKind.MULTI_AGENT, Attempt(files={"app/x.py": ""}, own_tests=TestTally(False)))
    quota = FixedSystem(SystemKind.SINGLE_AGENT, error=LLMUnavailableError("quota exhausted"))
    runner = BenchmarkRunner(sandbox=FakeSandbox(), repository=repository, model_name="m", demo_model=False)
    with pytest.raises(CapabilityUnavailableError, match="stopped serving"):
        runner.run("b1", [task()], [ok, quota])
    assert [r.system for r in repository.saved] == [SystemKind.MULTI_AGENT]  # the blocked attempt is not recorded


def test_runner_counts_findings_from_the_same_tools_for_every_system():
    blocking = Finding(FindingSeverity.HIGH, "security", "S602", "shell", FindingSource.TOOL, "app/x.py", 1)
    sandbox = FakeSandbox([passing_report()], findings=[blocking])
    files = {"app/x.py": 'API_KEY = "' + "sk_live_" + "a1b2c3d4e5f6g7h8i9j0k1l2" + '"\n'}
    runner = BenchmarkRunner(sandbox=sandbox, repository=None, model_name="m", demo_model=False)
    (row,) = runner.run("b1", [task()], [FixedSystem(SystemKind.MULTI_AGENT, Attempt(files=files, own_tests=TestTally(False)))])
    assert row.findings_total >= 2  # the secret scanner's finding plus the static analyser's
    assert row.blocking_findings >= 2


def test_runner_refuses_without_a_sandbox():
    system = FixedSystem(SystemKind.MULTI_AGENT, Attempt(files={}, own_tests=TestTally(False)))
    runner = BenchmarkRunner(sandbox=FakeSandbox(available=False), repository=None, model_name="m", demo_model=False)
    with pytest.raises(CapabilityUnavailableError):
        runner.run("b1", [task()], [system])
    assert system.calls == 0


def test_runner_reports_progress_for_every_task_and_system():
    seen = []
    systems = [FixedSystem(kind, Attempt(files={}, own_tests=TestTally(False))) for kind in SystemKind]
    runner = BenchmarkRunner(sandbox=FakeSandbox(), repository=None, model_name="m", demo_model=False)
    runner.run("b1", [task("a"), task("b")], systems, on_result=seen.append)
    assert [(r.task_id, r.system) for r in seen] == [(t, k) for t in ("a", "b") for k in SystemKind]


# ---------------------------------------------------------------- dataset loader


def test_dataset_loads_seven_tasks_with_hidden_reference_tests():
    tasks = load_tasks(DATASET)
    assert [t.id for t in tasks] == ["rest_api", "input_validation", "crud", "fix_bug", "write_tests", "add_auth", "db_schema"]
    assert [t.database for t in tasks] == [False] * 6 + [True]
    for t in tasks:
        assert t.reference_tests and all(p.startswith("tests/test_reference") for p in t.reference_tests)
        assert "test_reference" not in t.requirements, "prompts must not reveal the reference tests"


def test_loader_filters_and_rejects_unknown_ids():
    assert [t.id for t in load_tasks(DATASET, {"crud"})] == ["crud"]
    with pytest.raises(InvariantViolationError, match="nope"):
        load_tasks(DATASET, {"crud", "nope"})


def write_dataset(root: Path, tasks: list[dict], version=1) -> Path:
    (root / "t").mkdir(parents=True, exist_ok=True)
    (root / "t" / "prompt.md").write_text("Do it.", encoding="utf-8")
    (root / "t" / "test_ref.py").write_text("def test(): pass\n", encoding="utf-8")
    (root / "tasks.json").write_text(json.dumps({"version": version, "tasks": tasks}), encoding="utf-8")
    return root


def entry(**changes):
    return {"id": "t1", "title": "T", "category": "C", "prompt": "t/prompt.md", "reference_tests": ["t/test_ref.py"], **changes}


def test_loader_rejects_files_outside_the_dataset(tmp_path):
    (tmp_path / "secret.py").write_text("x", encoding="utf-8")
    root = write_dataset(tmp_path / "ds", [entry(reference_tests=["../secret.py"])])
    with pytest.raises(InvariantViolationError, match="inside"):
        load_tasks(root)


def test_loader_rejects_duplicates_and_unknown_versions(tmp_path):
    with pytest.raises(InvariantViolationError, match="unique"):
        load_tasks(write_dataset(tmp_path / "a", [entry(), entry()]))
    with pytest.raises(InvariantViolationError, match="version"):
        load_tasks(write_dataset(tmp_path / "b", [entry()], version=2))


# ---------------------------------------------------------------- break-it cases


@pytest.mark.parametrize("bad", ["", "../../etc/x", "a/b", "a\\b", "..", ".hidden", "-flag", "x" * 65, "white space", "ok..ok"])
def test_benchmark_ids_cannot_escape_or_overflow(bad):
    with pytest.raises(InvariantViolationError):
        validate_benchmark_id(bad)
    runner = BenchmarkRunner(sandbox=FakeSandbox(), repository=None, model_name="m", demo_model=False)
    with pytest.raises(InvariantViolationError):
        runner.run(bad, [task()], [])


@pytest.mark.parametrize("good", ["20261022-140000", "run1-qwen7b", "v1.2_final"])
def test_reasonable_benchmark_ids_are_accepted(good):
    assert validate_benchmark_id(good) == good


def test_a_systems_pytest_configuration_never_takes_part_in_grading():
    produced = {
        "app/__init__.py": "",
        "app/todos.py": "class TodoStore: ...\n",
        "app/sub/helpers.py": "x = 1\n",
        "conftest.py": "def pytest_collection_modifyitems(items): items.clear()\n",
        "app/conftest.py": "collect_ignore_glob = ['*']\n",
        "pytest.ini": "[pytest]\naddopts = -k nothing\n",
        "pyproject.toml": "[tool.pytest.ini_options]\naddopts = '-x'\n",
        "setup.cfg": "[tool:pytest]\n",
        "tox.ini": "[pytest]\n",
        "app/test_todos.py": "def test(): pass\n",
        "app/todos_test.py": "def test(): pass\n",
        "tests/test_mine.py": "def test(): pass\n",
        "README.md": "# hi\n",
        "helpers.py": "import sys\n",
    }
    assert set(grading_files(produced)) == {"app/__init__.py", "app/todos.py", "app/sub/helpers.py"}
    # A database task is graded with the system's migrations (and only those).
    with_sql = {**produced, "db/migrations/0001_initial.sql": "CREATE TABLE t (id INT);", "db/seed.py": "x", "db/migrations/notes.md": "x"}
    assert "db/migrations/0001_initial.sql" in grading_files(with_sql)
    assert not {"db/seed.py", "db/migrations/notes.md"} & set(grading_files(with_sql))


def test_runner_grades_without_a_systems_conftest():
    attempt = Attempt(files={"app/x.py": "x = 1\n", "conftest.py": "boom"}, own_tests=TestTally(False))
    sandbox = FakeSandbox()
    BenchmarkRunner(sandbox=sandbox, repository=None, model_name="m", demo_model=False).run(
        "b1", [task()], [FixedSystem(SystemKind.MULTI_AGENT, attempt)]
    )
    assert "conftest.py" not in sandbox.test_calls[-1]


class DyingSandbox(FakeSandbox):
    """Available at the start, then Docker stops."""

    def run_tests(self, files, *, database=False):
        self.test_calls.append(dict(files))
        if len(self.test_calls) > 1:
            return TestReport(executed=False, command="pytest", unavailable_reason="Docker daemon is not running")
        return passing_report()


def test_benchmark_stops_when_the_sandbox_dies_instead_of_recording_not_run():
    repository = RecordingRepository()
    system = FixedSystem(SystemKind.SINGLE_AGENT, Attempt(files={"app/x.py": ""}, own_tests=TestTally(False)))
    runner = BenchmarkRunner(sandbox=DyingSandbox(), repository=repository, model_name="m", demo_model=False)
    with pytest.raises(CapabilityUnavailableError, match="stopped"):
        runner.run("b1", [task("a"), task("b")], [system])
    assert [r.task_id for r in repository.saved] == ["a"], "finished rows are kept, the ungraded one is not saved"


@pytest.mark.parametrize(
    "breakage, match",
    [
        (lambda root: (root / "tasks.json").unlink(), "cannot read"),
        (lambda root: (root / "tasks.json").write_text("{not json", encoding="utf-8"), "cannot read"),
        (lambda root: (root / "tasks.json").write_bytes(b"\xff\xfe\x00bad"), "cannot read"),
        (lambda root: (root / "tasks.json").write_text('{"version": 1, "tasks": [{"id": "t1"}]}', encoding="utf-8"), "malformed"),
        (lambda root: (root / "tasks.json").write_text('{"version": 1}', encoding="utf-8"), "malformed"),
        (lambda root: (root / "t" / "prompt.md").unlink(), "inside"),
    ],
)
def test_a_broken_dataset_is_reported_clearly(tmp_path, breakage, match):
    root = write_dataset(tmp_path, [entry()])
    breakage(root)
    with pytest.raises(InvariantViolationError, match=match):
        load_tasks(root)


# ---------------------------------------------------------------- composition


def test_benchmark_refuses_without_a_model():
    with pytest.raises(CapabilityUnavailableError, match="no model"):
        build_benchmark(make_settings("sqlite://"), persist=False, sandbox=FakeSandbox())


def test_benchmark_refuses_the_scripted_demo_model():
    with pytest.raises(CapabilityUnavailableError, match="not AI"):
        build_benchmark(make_settings("sqlite://"), persist=False, llm=ScriptedLLM(), sandbox=FakeSandbox())


def test_benchmark_wires_both_systems():
    benchmark = build_benchmark(make_settings("sqlite://"), persist=False, llm=ScenarioLLM(), sandbox=FakeSandbox())
    assert set(benchmark.systems) == set(SystemKind)
    results = benchmark.runner.run("b1", [task()], list(benchmark.systems.values()))
    assert {r.system for r in results} == set(SystemKind)
