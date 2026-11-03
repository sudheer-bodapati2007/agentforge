"""Persistence and execution ports for workflow runs."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.application.runs.models import (
    AgentExecutionView,
    ApprovalView,
    ArtifactView,
    ClaimedRun,
    EventView,
    FindingView,
    RunView,
    TestResultView,
)
from app.application.workflow.state import WorkflowState
from app.domain.enums import ApprovalStatus, RunStatus


class RunRepository(Protocol):
    # --- commands issued by users (always owner-scoped) -------------------------
    def create(
        self,
        *,
        project_id: uuid.UUID,
        requested_by: uuid.UUID,
        require_approval: bool,
        max_debug_iterations: int,
        max_review_corrections: int,
        idempotency_key: str | None,
        llm_model: str,
        demo_model: bool,
    ) -> RunView: ...

    def find_by_idempotency_key(self, owner_id: uuid.UUID, project_id: uuid.UUID, key: str) -> RunView | None: ...

    def get_for_owner(self, owner_id: uuid.UUID, run_id: uuid.UUID) -> RunView | None: ...

    def list_for_owner(
        self, owner_id: uuid.UUID, *, project_id: uuid.UUID | None, status: RunStatus | None, limit: int, offset: int
    ) -> tuple[list[RunView], int]: ...

    def count_active_for_owner(self, owner_id: uuid.UUID) -> int: ...

    def count_created_since(self, owner_id: uuid.UUID, since: datetime) -> int: ...

    def request_cancel(self, run_id: uuid.UUID) -> RunView: ...

    def decide_approval(
        self,
        run_id: uuid.UUID,
        approval_id: uuid.UUID,
        status: ApprovalStatus,
        comment: str | None,
    ) -> ApprovalView: ...

    def requeue(self, run_id: uuid.UUID, resume_payload: dict[str, Any] | None) -> RunView: ...

    # --- queue operations used by workers --------------------------------------
    def claim_next(self, worker_id: str) -> ClaimedRun | None:
        """Atomically move the oldest queued run to running for this worker."""
        ...

    def heartbeat(self, run_id: uuid.UUID, worker_id: str) -> None: ...

    def mark_awaiting_approval(self, run_id: uuid.UUID, ticket: dict[str, Any]) -> None: ...

    def finish(
        self,
        run_id: uuid.UUID,
        status: RunStatus,
        *,
        error: str | None = None,
        final_report: dict[str, Any] | None = None,
    ) -> None: ...

    def requeue_stale(self, older_than: datetime) -> int:
        """Return runs whose worker stopped heartbeating to the queue (crash recovery)."""
        ...

    # --- read models -------------------------------------------------------------
    def events_after(self, run_id: uuid.UUID, after_id: int, limit: int) -> list[EventView]: ...

    def agent_executions(self, run_id: uuid.UUID) -> list[AgentExecutionView]: ...

    def artifacts(self, run_id: uuid.UUID) -> list[ArtifactView]: ...

    def artifact_contents(self, run_id: uuid.UUID) -> dict[str, str]: ...

    def test_results(self, run_id: uuid.UUID) -> list[TestResultView]: ...

    def findings(self, run_id: uuid.UUID) -> list[FindingView]: ...

    def approvals(self, run_id: uuid.UUID) -> list[ApprovalView]: ...


@dataclass(frozen=True)
class EngineOutcome:
    interrupted: bool
    state: dict[str, Any]
    interrupt: dict[str, Any] | None = None


class WorkflowEngine(Protocol):
    def execute(
        self, run_id: str, initial_state: WorkflowState, resume: dict[str, Any] | None
    ) -> EngineOutcome:
        """Start a run, continue it from its checkpoint, or resume it with a human decision."""
        ...


class RunNotifier(Protocol):
    """Wakes idle workers when new work is queued (an optimisation; polling still works)."""

    def notify(self) -> None: ...
