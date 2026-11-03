"""Benchmark rules: how one attempt at a task is scored and how scores aggregate.

Every score comes from an executed test run. A system's *own* tests only show that its
code agrees with its own tests; the task's *reference* tests (written by people, hidden
from the systems, run in the same sandbox) are the correctness measure. Aggregates that
have nothing to divide by are None, never 0.
"""

import re
import statistics
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.errors import InvariantViolationError
from app.domain.testing import TestReport
from app.domain.workspace import normalize_path

_TASK_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_BENCHMARK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# Files that change how pytest collects or runs tests. A system's copy of any of these
# must never take part in grading it.
_PYTEST_CONTROL = frozenset({"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"})


def validate_benchmark_id(value: str) -> str:
    """Benchmark ids name report files and database rows: short, and no path characters."""
    if not _BENCHMARK_ID.match(value) or ".." in value:
        raise InvariantViolationError("benchmark_id", "use 1-64 letters, digits, '.', '_' or '-', not starting with a symbol")
    return value


def grading_files(files: dict[str, str]) -> dict[str, str]:
    """The part of a system's output the reference tests run against: its application code
    under app/ and its SQL migrations, without its own tests or anything that reconfigures
    pytest."""
    kept = {}
    for path, content in files.items():
        name = path.rsplit("/", 1)[-1]
        if path.startswith("db/migrations/") and name.endswith(".sql"):
            kept[path] = content
            continue
        if not path.startswith("app/") or name in _PYTEST_CONTROL:
            continue
        if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
            continue
        kept[path] = content
    return kept


class SystemKind(StrEnum):
    MULTI_AGENT = "multi_agent"
    SINGLE_AGENT = "single_agent"


@dataclass(frozen=True)
class EvaluationTask:
    id: str
    title: str
    category: str
    requirements: str
    reference_tests: dict[str, str] = field(default_factory=dict)
    # The task needs a PostgreSQL database: systems get one, and grading runs against one.
    database: bool = False

    def __post_init__(self) -> None:
        if not _TASK_ID.match(self.id):
            raise InvariantViolationError("id", f"invalid task id {self.id!r}")
        if not self.requirements.strip():
            raise InvariantViolationError("requirements", f"task {self.id} has no requirements")
        if not self.reference_tests:
            raise InvariantViolationError("reference_tests", f"task {self.id} has no reference tests")
        for path in self.reference_tests:
            if normalize_path(path) != path or not path.startswith("tests/"):
                raise InvariantViolationError("reference_tests", f"reference test {path!r} must be a normalised path under tests/")


@dataclass(frozen=True)
class TestTally:
    """Counts from one executed (or not executed) test run."""

    __test__ = False

    executed: bool
    passed: int = 0
    total: int = 0
    errors: int = 0

    @classmethod
    def of(cls, report: TestReport | None) -> "TestTally":
        if report is None:
            return cls(executed=False)
        return cls(executed=report.executed, passed=report.passed, total=report.total, errors=report.errors)

    @property
    def succeeded(self) -> bool:
        return self.executed and self.total > 0 and self.passed == self.total and self.errors == 0

    @property
    def pass_fraction(self) -> float | None:
        """None when the suite never ran; 0.0 when it ran but nothing passed (e.g. an
        import error stopped collection)."""
        if not self.executed:
            return None
        return self.passed / self.total if self.total else 0.0


@dataclass(frozen=True)
class EvaluationResult:
    benchmark_id: str
    task_id: str
    task_title: str
    category: str
    system: SystemKind
    model_name: str
    demo_model: bool
    own_tests: TestTally
    reference_tests: TestTally
    debug_iterations: int
    test_runs: int
    findings_total: int
    blocking_findings: int
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    human_interventions: int
    error: str | None = None

    @property
    def solved(self) -> bool:
        """A task is solved only when every hidden reference test passes."""
        return self.reference_tests.succeeded


@dataclass(frozen=True)
class SystemSummary:
    system: SystemKind
    tasks: int
    solved: int
    solve_rate: float | None
    reference_pass_rate: float | None
    own_suite_success_rate: float | None
    mean_debug_iterations: float | None
    median_latency_seconds: float | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float | None
    blocking_findings: int
    errors: int


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(results: list[EvaluationResult]) -> list[SystemSummary]:
    """One summary per system present, in SystemKind order."""
    summaries = []
    for system in SystemKind:
        rows = [r for r in results if r.system is system]
        if not rows:
            continue
        costs = [r.estimated_cost_usd for r in rows]
        summaries.append(
            SystemSummary(
                system=system,
                tasks=len(rows),
                solved=sum(r.solved for r in rows),
                solve_rate=sum(r.solved for r in rows) / len(rows),
                # Mean of per-task fractions, so a task whose code cannot even be imported
                # counts as 0 instead of silently dropping out of a pooled ratio.
                reference_pass_rate=_mean([f for r in rows if (f := r.reference_tests.pass_fraction) is not None]),
                own_suite_success_rate=_mean([float(r.own_tests.succeeded) for r in rows if r.own_tests.executed]),
                mean_debug_iterations=_mean([float(r.debug_iterations) for r in rows]),
                median_latency_seconds=statistics.median(r.latency_seconds for r in rows),
                total_input_tokens=sum(r.input_tokens for r in rows),
                total_output_tokens=sum(r.output_tokens for r in rows),
                # A total is only meaningful when every row has a known cost.
                total_cost_usd=None if any(c is None for c in costs) else round(sum(costs), 6),  # type: ignore[arg-type]
                blocking_findings=sum(r.blocking_findings for r in rows),
                errors=sum(r.error is not None for r in rows),
            )
        )
    return summaries
