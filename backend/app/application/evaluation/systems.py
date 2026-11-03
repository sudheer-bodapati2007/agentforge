"""The two systems the benchmark compares, behind the `CodingSystem` port.

Both receive exactly the same request text and run their tests in the same sandbox.
"""

import uuid
from collections.abc import Callable
from typing import Any

from app.application.agents import prompts
from app.application.agents.schemas import CodeChangeSet
from app.application.llm import StructuredLLM, TokenUsage
from app.application.evaluation.ports import Attempt
from app.application.runs.ports import WorkflowEngine
from app.application.workflow.ports import Sandbox
from app.application.workflow.state import WorkflowState
from app.application.workflow.steps import PACKAGE_INIT
from app.domain.enums import AgentRole
from app.domain.errors import InvariantViolationError
from app.domain.evaluation import EvaluationTask, SystemKind, TestTally
from app.domain.workspace import SourceFile, merge_files

EVALUATION_OWNER = "evaluation"


class SingleAgentBaseline:
    """One model call that writes code and tests together; no plan, review or debugging."""

    kind = SystemKind.SINGLE_AGENT

    def __init__(self, *, llm: StructuredLLM, sandbox: Sandbox) -> None:
        self._llm = llm
        self._sandbox = sandbox

    def solve(self, task: EvaluationTask) -> Attempt:
        user = prompts.single_agent_user(task.requirements)
        result = self._llm.generate(
            task="single_agent",
            system=prompts.SINGLE_AGENT_SYSTEM,
            # Same environment description the agents get, so the comparison stays fair.
            user=f"{user}\n\n{prompts.DATABASE_ENVIRONMENT}" if task.database else user,
            schema=CodeChangeSet,
        )
        files = validated_files(result.value.files)
        report = self._sandbox.run_tests(files, database=task.database)
        return Attempt(files=files, own_tests=TestTally.of(report), test_runs=1, usage=result.usage)


def validated_files(proposed: list) -> dict[str, str]:
    """The same path and size rules the agents' writes go through; invalid files are
    dropped, and the package marker is added exactly as the coding agent's is."""
    accepted = []
    for item in proposed:
        try:
            accepted.append(SourceFile.create(item.path, item.content))
        except InvariantViolationError:
            continue
    files = merge_files({}, accepted)
    if not any(path.startswith("app/") for path in files):
        raise InvariantViolationError("files", "the model produced no valid source files under app/")
    files.setdefault(PACKAGE_INIT, "")
    return files


class MultiAgentWorkflow:
    """The full AgentForge graph, with approvals switched off (no human in the loop)."""

    kind = SystemKind.MULTI_AGENT

    def __init__(
        self,
        *,
        engine: WorkflowEngine,
        max_debug_iterations: int,
        max_review_corrections: int,
        run_ids: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._engine = engine
        self._max_debug = max_debug_iterations
        self._max_corrections = max_review_corrections
        self._run_ids = run_ids

    def solve(self, task: EvaluationTask) -> Attempt:
        run_id = self._run_ids()
        outcome = self._engine.execute(run_id, self._initial_state(run_id, task), None)
        if outcome.interrupted:
            raise RuntimeError("the workflow paused for a human decision; benchmark runs must not require approval")
        final = outcome.state
        report = final.get("test_report") or {}
        usage = final.get("usage") or {}
        return Attempt(
            files=dict(final.get("files") or {}),
            own_tests=TestTally(
                executed=bool(report.get("executed")),
                passed=report.get("passed", 0),
                total=report.get("total", 0),
                errors=report.get("errors", 0),
            ),
            debug_iterations=final.get("debug_iterations", 0),
            test_runs=final.get("test_attempt", 0),
            usage=TokenUsage(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
        )

    def _initial_state(self, run_id: str, task: EvaluationTask) -> WorkflowState:
        return WorkflowState(
            run_id=run_id,
            project_id=f"evaluation-{task.id}",
            owner_id=EVALUATION_OWNER,
            requirements=task.requirements,
            preferences={"language": "python", "database": "PostgreSQL" if task.database else None},
            require_approval=False,
            max_debug_iterations=self._max_debug,
            max_review_corrections=self._max_corrections,
            database=task.database,
            plan_revisions=0,
            test_attempt=0,
            debug_iterations=0,
            debug_history=[],
            memory=[],
            review_cycle=0,
            corrections_applied=0,
            files={},
            usage={"input_tokens": 0, "output_tokens": 0},
        )


class EvaluationJournal:
    """A `RunJournal` that keeps a benchmark run's events in memory. Benchmark runs are not
    user runs, so nothing is written to the runs tables."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[dict[str, Any]] = []

    def is_cancel_requested(self) -> bool:
        return False

    def step_started(self, node: str, agent: AgentRole | None, attempt: int) -> None:
        pass

    def step_finished(self, node, agent, attempt, summary, usage) -> None:
        self.events.append({"type": "step.finished", "node": node, "attempt": attempt, "summary": summary})

    def step_failed(self, node, agent, attempt, error) -> None:
        self.events.append({"type": "step.failed", "node": node, "attempt": attempt, "error": error})

    def emit(self, event_type: str, node: str | None = None, **payload: Any) -> None:
        self.events.append({"type": event_type, "node": node, **payload})

    def save_files(self, files, author) -> None:
        pass

    def save_test_report(self, attempt, report) -> None:
        pass

    def save_findings(self, cycle, findings) -> None:
        pass

    def ensure_approval(self, **_: Any):
        raise RuntimeError("benchmark runs never request approval")
