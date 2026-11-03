"""The benchmark command (evals/scripts/run_benchmark.py) with fake wiring: argument
validation, reports, and what happens when a run is interrupted."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.application.evaluation.benchmark import BenchmarkRunner
from app.application.evaluation.ports import Attempt
from app.bootstrap import Benchmark
from app.domain.evaluation import SystemKind, TestTally
from tests.conftest import make_settings
from tests.fakes import FakeSandbox

SCRIPT = Path(__file__).resolve().parents[3] / "evals" / "scripts" / "run_benchmark.py"
_spec = importlib.util.spec_from_file_location("run_benchmark", SCRIPT)
command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(command)


class System:
    def __init__(self, kind, interrupt_on=None):
        self.kind = kind
        self.interrupt_on = interrupt_on

    def solve(self, task):
        if task.id == self.interrupt_on:
            raise KeyboardInterrupt
        return Attempt(files={"app/x.py": "x = 1\n"}, own_tests=TestTally(executed=True, passed=1, total=1))


def fake_build(interrupt_on=None, built=None):
    def build(settings, persist):
        runner = BenchmarkRunner(sandbox=FakeSandbox(), repository=None, model_name="fake-model", demo_model=False)
        systems = {kind: System(kind, interrupt_on) for kind in SystemKind}
        if built is not None:
            built.append(persist)
        return Benchmark(runner=runner, systems=systems, close=lambda: None)

    return build


def run(tmp_path, *extra, build=None):
    argv = ["--report-dir", str(tmp_path), "--benchmark-id", "unit-1", *extra]
    return command.main(argv, settings=make_settings("sqlite://"), build=build or fake_build())


def test_writes_a_complete_report(tmp_path, capsys):
    assert run(tmp_path, "--tasks", "crud,fix_bug") == 0
    report = json.loads((tmp_path / "unit-1.json").read_text(encoding="utf-8"))
    assert report["complete"] is True and report["model"] == "fake-model"
    assert [(r["task_id"], r["system"]) for r in report["results"]] == [
        ("crud", "multi_agent"), ("crud", "single_agent"), ("fix_bug", "multi_agent"), ("fix_bug", "single_agent")
    ]
    assert all(r["solved"] for r in report["results"])
    assert [s["system"] for s in report["summaries"]] == ["multi_agent", "single_agent"]
    assert "summary" in capsys.readouterr().out
    attempt = tmp_path / "unit-1" / "crud" / "single_agent"
    assert (attempt / "files" / "app" / "x.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (attempt / "reference_tests.txt").read_text(encoding="utf-8").startswith("3/3 passed")


def test_saved_attempt_files_cannot_escape_the_report_folder(tmp_path):
    from app.application.evaluation.benchmark import GradedAttempt
    from app.domain.errors import InvariantViolationError
    from tests.fakes import passing_report
    from tests.unit.test_evaluation import result

    graded = GradedAttempt(result=result(), files={"../../outside.py": "x"}, reference_report=passing_report())
    with pytest.raises(InvariantViolationError):
        command.save_attempt(tmp_path / "bench", graded)
    assert not (tmp_path / "outside.py").exists()


def test_interrupt_keeps_the_finished_results(tmp_path):
    assert run(tmp_path, "--tasks", "crud,fix_bug", build=fake_build(interrupt_on="fix_bug")) == 130
    report = json.loads((tmp_path / "unit-1.json").read_text(encoding="utf-8"))
    assert report["complete"] is False
    assert {r["task_id"] for r in report["results"]} == {"crud"}


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--benchmark-id", "../../escape"], "benchmark_id"),
        (["--tasks", "nope"], "unknown task"),
        (["--systems", "multi_agent,gpt"], "gpt"),
    ],
)
def test_bad_arguments_fail_before_any_model_call(tmp_path, capsys, argv, message):
    built = []
    assert command.main(["--report-dir", str(tmp_path), *argv], settings=make_settings("sqlite://"), build=fake_build(built=built)) == 2
    assert message in capsys.readouterr().err
    assert built == [], "nothing was wired, so no model was called"
    assert list(tmp_path.iterdir()) == []


def test_no_db_skips_persistence(tmp_path):
    built = []
    run(tmp_path, "--tasks", "crud", "--no-db", build=fake_build(built=built))
    assert built == [False]
