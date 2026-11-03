"""Read models and commands for workflow runs."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.enums import AgentExecutionStatus, AgentRole, ApprovalStatus, RunStatus


@dataclass(frozen=True)
class RunView:
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    status: RunStatus
    current_node: str | None
    require_approval: bool
    cancel_requested: bool
    debug_iterations: int
    max_debug_iterations: int
    llm_model: str | None
    demo_model: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    final_report: dict[str, Any] | None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


@dataclass(frozen=True)
class ClaimedRun:
    """A run a worker has exclusively claimed, plus everything needed to execute it."""

    run: RunView
    owner_id: uuid.UUID
    requirements: str
    preferences: dict[str, Any]
    max_review_corrections: int
    resume_payload: dict[str, Any] | None
    is_continuation: bool  # started before: resume from the checkpoint


@dataclass(frozen=True)
class CreateRunCommand:
    require_approval: bool = True
    idempotency_key: str | None = None


@dataclass(frozen=True)
class EventView:
    id: int
    type: str
    node: str | None
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class AgentExecutionView:
    id: uuid.UUID
    node: str
    agent: AgentRole | None
    attempt: int
    status: AgentExecutionStatus
    summary: str | None
    error: str | None
    input_tokens: int
    output_tokens: int
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class ArtifactView:
    path: str
    kind: str
    sha256: str
    size_bytes: int
    created_by: AgentRole | None
    updated_at: datetime


@dataclass(frozen=True)
class TestResultView:
    __test__ = False

    attempt: int
    command: str
    executed: bool
    exit_code: int | None
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_ms: int | None
    output_excerpt: str | None
    failures: list[dict[str, Any]] = field(default_factory=list)
    unavailable_reason: str | None = None
    database: dict[str, Any] | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class FindingView:
    id: uuid.UUID
    cycle: int
    severity: str
    category: str
    title: str
    description: str
    file_path: str | None
    line: int | None
    suggestion: str | None
    source: str
    tool_name: str | None


@dataclass(frozen=True)
class ApprovalView:
    id: uuid.UUID
    kind: str
    cycle: int
    status: ApprovalStatus
    reason: str
    affected_resources: list[str]
    security_notes: str | None
    details: dict[str, Any]
    decision_comment: str | None
    requested_at: datetime
    decided_at: datetime | None
