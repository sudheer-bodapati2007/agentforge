"""Run use cases: start, observe, approve, cancel and resume workflow runs."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.llm import LLMError
from app.application.runs.models import (
    AgentExecutionView,
    ApprovalView,
    ArtifactView,
    CreateRunCommand,
    EventView,
    FindingView,
    RunView,
    TestResultView,
)
from app.application.runs.ports import RunNotifier, RunRepository
from app.domain.enums import ApprovalStatus, ProgrammingLanguage, RunStatus
from app.domain.errors import (
    CapabilityUnavailableError,
    ConflictError,
    EntityNotFoundError,
    InvariantViolationError,
    RateLimitedError,
)
from app.domain.ports import ProjectRepository
from app.domain.run import is_terminal
from app.domain.user import User

EXECUTABLE_LANGUAGES = frozenset({ProgrammingLanguage.PYTHON})


@dataclass(frozen=True)
class RunPolicy:
    max_debug_iterations: int
    max_review_corrections: int
    max_active_runs_per_user: int
    max_runs_per_user_per_hour: int


@dataclass(frozen=True)
class ModelInfo:
    configured: bool
    name: str
    demo: bool
    detail: str | None = None


class RunService:
    def __init__(
        self,
        *,
        runs: RunRepository,
        projects: ProjectRepository,
        policy: RunPolicy,
        model: ModelInfo,
        notifier: RunNotifier | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._runs = runs
        self._projects = projects
        self._policy = policy
        self._model = model
        self._notifier = notifier
        self._clock = clock

    # ------------------------------------------------------------------ commands

    def start(self, actor: User, project_id: uuid.UUID, command: CreateRunCommand) -> tuple[RunView, bool]:
        """Returns (run, created). Re-sending the same idempotency key returns the original run."""
        project = self._projects.get(actor.id, project_id)
        if project is None:
            raise EntityNotFoundError("Project", project_id)

        if command.idempotency_key:
            existing = self._runs.find_by_idempotency_key(actor.id, project_id, command.idempotency_key)
            if existing:
                return existing, False

        if project.language not in EXECUTABLE_LANGUAGES:
            raise InvariantViolationError(
                "language", "only Python projects can be executed by this version of AgentForge"
            )
        if not self._model.configured:
            raise CapabilityUnavailableError(self._model.detail or "No LLM provider is configured")

        if self._runs.count_active_for_owner(actor.id) >= self._policy.max_active_runs_per_user:
            raise RateLimitedError(
                f"You already have {self._policy.max_active_runs_per_user} active run(s); wait for one to finish."
            )
        hour_ago = self._clock() - timedelta(hours=1)
        if self._runs.count_created_since(actor.id, hour_ago) >= self._policy.max_runs_per_user_per_hour:
            raise RateLimitedError("Hourly run limit reached; try again later.", retry_after_seconds=600)

        run = self._runs.create(
            project_id=project_id,
            requested_by=actor.id,
            require_approval=command.require_approval,
            max_debug_iterations=self._policy.max_debug_iterations,
            max_review_corrections=self._policy.max_review_corrections,
            idempotency_key=command.idempotency_key,
            llm_model=self._model.name,
            demo_model=self._model.demo,
        )
        self._notify()
        return run, True

    def cancel(self, actor: User, run_id: uuid.UUID) -> RunView:
        run = self.get(actor, run_id)
        if is_terminal(run.status):
            raise ConflictError(f"Run is already {run.status.value}")
        return self._runs.request_cancel(run_id)

    def decide(
        self, actor: User, run_id: uuid.UUID, approval_id: uuid.UUID, approve: bool, comment: str | None
    ) -> ApprovalView:
        run = self.get(actor, run_id)
        if run.status is not RunStatus.AWAITING_APPROVAL:
            raise ConflictError("This run is not waiting for approval")
        pending = [a for a in self._runs.approvals(run_id) if a.status is ApprovalStatus.PENDING]
        if not any(a.id == approval_id for a in pending):
            raise ConflictError("This approval request is not pending")
        status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        ticket = self._runs.decide_approval(run_id, approval_id, status, comment)
        # The worker resumes the paused graph with exactly this decision.
        self._runs.requeue(run_id, {"decision": status.value, "comment": comment or "", "approval_id": str(approval_id)})
        self._notify()
        return ticket

    def resume(self, actor: User, run_id: uuid.UUID) -> RunView:
        """Retry a failed run from its last checkpoint (completed steps are not repeated)."""
        run = self.get(actor, run_id)
        if run.status is not RunStatus.FAILED:
            raise ConflictError("Only failed runs can be resumed")
        if not self._model.configured:
            raise CapabilityUnavailableError(self._model.detail or "No LLM provider is configured")
        resumed = self._runs.requeue(run_id, None)
        self._notify()
        return resumed

    # --------------------------------------------------------------------- reads

    def get(self, actor: User, run_id: uuid.UUID) -> RunView:
        run = self._runs.get_for_owner(actor.id, run_id)
        if run is None:
            raise EntityNotFoundError("Run", run_id)
        return run

    def list_runs(
        self,
        actor: User,
        *,
        project_id: uuid.UUID | None = None,
        status: RunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RunView], int]:
        return self._runs.list_for_owner(actor.id, project_id=project_id, status=status, limit=limit, offset=offset)

    def events(self, actor: User, run_id: uuid.UUID, after_id: int = 0, limit: int = 500) -> list[EventView]:
        self.get(actor, run_id)
        return self._runs.events_after(run_id, after_id, limit)

    def agent_executions(self, actor: User, run_id: uuid.UUID) -> list[AgentExecutionView]:
        self.get(actor, run_id)
        return self._runs.agent_executions(run_id)

    def artifacts(self, actor: User, run_id: uuid.UUID) -> list[ArtifactView]:
        self.get(actor, run_id)
        return self._runs.artifacts(run_id)

    def artifact_contents(self, actor: User, run_id: uuid.UUID) -> dict[str, str]:
        self.get(actor, run_id)
        return self._runs.artifact_contents(run_id)

    def test_results(self, actor: User, run_id: uuid.UUID) -> list[TestResultView]:
        self.get(actor, run_id)
        return self._runs.test_results(run_id)

    def findings(self, actor: User, run_id: uuid.UUID) -> list[FindingView]:
        self.get(actor, run_id)
        return self._runs.findings(run_id)

    def approvals(self, actor: User, run_id: uuid.UUID) -> list[ApprovalView]:
        self.get(actor, run_id)
        return self._runs.approvals(run_id)

    def _notify(self) -> None:
        if self._notifier:
            self._notifier.notify()


def public_error(exc: BaseException) -> str:
    """A failure message safe to show users: known error types only, never internals."""
    if isinstance(exc, (LLMError, InvariantViolationError, CapabilityUnavailableError)):
        return str(exc)[:500]
    return "The workflow stopped because of an internal error. Details are in the server logs."


def run_preferences(language: str, framework: str | None, database: str | None, constraints: str | None) -> dict[str, Any]:
    return {
        "language": language,
        "framework": framework,
        "database": database,
        "constraints": constraints,
    }
