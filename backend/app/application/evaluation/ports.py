"""Ports for the evaluation benchmark. Implementations live in infrastructure/."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.application.llm import TokenUsage
from app.domain.evaluation import EvaluationResult, EvaluationTask, SystemKind, TestTally


@dataclass(frozen=True)
class Attempt:
    """What a system produced for one task. `own_tests` is the system's own final test
    run as reported by the sandbox (not executed if the system never ran its tests)."""

    files: dict[str, str]
    own_tests: TestTally
    debug_iterations: int = 0
    test_runs: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    human_interventions: int = 0


class CodingSystem(Protocol):
    """A way of turning a software request into code and tests (multi-agent, baseline)."""

    @property
    def kind(self) -> SystemKind: ...

    def solve(self, task: EvaluationTask) -> Attempt: ...


@dataclass(frozen=True)
class StoredBenchmark:
    id: str
    created_at: datetime
    results: list[EvaluationResult]


class EvaluationRepository(Protocol):
    def save(self, result: EvaluationResult) -> None:
        """Idempotent upsert keyed by (benchmark_id, task_id, system): re-running a task
        in the same benchmark replaces its row instead of duplicating it."""
        ...

    def recent_benchmarks(self, limit: int) -> list[StoredBenchmark]:
        """Newest first."""
        ...
