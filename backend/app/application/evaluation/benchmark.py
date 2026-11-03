"""Benchmark use case: run every task through every system and grade the results.

Grading is identical for every system and never trusts the system itself:
  - correctness: the task's hidden reference tests, run in the sandbox against the
    system's application code only (its own tests, conftest.py and pytest configuration
    are removed first, so they cannot deselect, skip or add tests);
  - code findings: the same secret scanner and static analysers on the final files;
  - latency: wall clock around `solve`; tokens: as reported by the model provider.
A system that crashes is recorded as an unsolved attempt with the error, so one bad
model answer cannot abort or silently shrink a benchmark.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.application.evaluation.ports import Attempt, CodingSystem, EvaluationRepository
from app.application.llm import LLMUnavailableError, Pricing
from app.application.workflow.ports import Sandbox
from app.application.workflow.secret_scanner import scan_for_secrets
from app.domain.errors import CapabilityUnavailableError
from app.domain.evaluation import EvaluationResult, EvaluationTask, TestTally, grading_files, validate_benchmark_id
from app.domain.testing import TestReport

logger = logging.getLogger("agentforge.evaluation")

MAX_ERROR_CHARS = 500


@dataclass(frozen=True)
class GradedAttempt:
    """Everything behind one result, for inspection: what the system produced and the raw
    output of the reference test run that graded it."""

    result: EvaluationResult
    files: dict[str, str]
    reference_report: TestReport


class BenchmarkRunner:
    def __init__(
        self,
        *,
        sandbox: Sandbox,
        repository: EvaluationRepository | None,
        model_name: str,
        demo_model: bool,
        pricing: Pricing | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sandbox = sandbox
        self._repository = repository
        self._model_name = model_name
        self._demo_model = demo_model
        self._pricing = pricing
        self._clock = clock

    def run(
        self,
        benchmark_id: str,
        tasks: list[EvaluationTask],
        systems: list[CodingSystem],
        on_result: Callable[[EvaluationResult], None] | None = None,
        on_graded: Callable[[GradedAttempt], None] | None = None,
    ) -> list[EvaluationResult]:
        validate_benchmark_id(benchmark_id)
        status = self._sandbox.status()
        if not status.available:
            # Without the sandbox nothing can be graded; refusing beats reporting zeros.
            raise CapabilityUnavailableError(f"the sandbox is required to grade a benchmark: {status.detail}")
        results = []
        for task in tasks:
            for system in systems:
                graded = self.evaluate(benchmark_id, task, system)
                if self._repository is not None:
                    self._repository.save(graded.result)
                if on_graded is not None:
                    on_graded(graded)
                if on_result is not None:
                    on_result(graded.result)
                results.append(graded.result)
        return results

    def evaluate(self, benchmark_id: str, task: EvaluationTask, system: CodingSystem) -> GradedAttempt:
        started = self._clock()
        error = None
        try:
            attempt = system.solve(task)
        except LLMUnavailableError as exc:
            # Quota, rate limit or a rejected key: nothing to do with the model's ability, so
            # stop instead of recording an unsolved task. Finished rows are already saved.
            raise CapabilityUnavailableError(f"the model provider stopped serving requests: {exc}") from exc
        except Exception as exc:  # recorded, not raised: see module docstring
            logger.warning("task=%s system=%s failed: %s", task.id, system.kind, exc)
            error = (str(exc) or exc.__class__.__name__)[:MAX_ERROR_CHARS]
            attempt = Attempt(files={}, own_tests=TestTally(executed=False))
        latency = self._clock() - started

        reference = self._sandbox.run_tests({**grading_files(attempt.files), **task.reference_tests}, database=task.database)
        if not reference.executed:
            # The sandbox went away mid-benchmark. Recording "not run" would quietly drop
            # this task from the averages, so stop instead; finished rows are already saved.
            raise CapabilityUnavailableError(f"the sandbox stopped during the benchmark: {reference.unavailable_reason}")
        findings = (scan_for_secrets(attempt.files) + self._sandbox.run_static_analysis(attempt.files)) if attempt.files else []

        result = EvaluationResult(
            benchmark_id=benchmark_id,
            task_id=task.id,
            task_title=task.title,
            category=task.category,
            system=system.kind,
            model_name=self._model_name,
            demo_model=self._demo_model,
            own_tests=attempt.own_tests,
            reference_tests=TestTally.of(reference),
            debug_iterations=attempt.debug_iterations,
            test_runs=attempt.test_runs,
            findings_total=len(findings),
            blocking_findings=sum(f.blocking for f in findings),
            latency_seconds=round(latency, 3),
            input_tokens=attempt.usage.input_tokens,
            output_tokens=attempt.usage.output_tokens,
            estimated_cost_usd=round(self._pricing.cost(attempt.usage), 6) if self._pricing else None,
            human_interventions=attempt.human_interventions,
            error=error,
        )
        return GradedAttempt(result=result, files=attempt.files, reference_report=reference)
