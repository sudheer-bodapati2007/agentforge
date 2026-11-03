import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AgentExecutionStatus, AgentRole, ApprovalStatus, RunStatus


class _FromAttrs(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_approval: bool = Field(default=True, description="Pause for human approval before code generation")


class RunRead(_FromAttrs):
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
    duration_seconds: float | None
    error: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    final_report: dict[str, Any] | None


class RunList(BaseModel):
    items: list[RunRead]
    total: int


class EventRead(_FromAttrs):
    id: int
    type: str
    node: str | None
    payload: dict[str, Any]
    created_at: datetime


class AgentExecutionRead(_FromAttrs):
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


class ArtifactRead(_FromAttrs):
    path: str
    kind: str
    sha256: str
    size_bytes: int
    created_by: AgentRole | None
    updated_at: datetime


class ArtifactContent(BaseModel):
    path: str
    content: str


class TestResultRead(_FromAttrs):
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
    failures: list[dict[str, Any]]
    unavailable_reason: str | None
    # {migrations: [{file, ok, error}], schema: [{name, columns, foreign_keys, unique, indexes}], error}
    database: dict[str, Any] | None = None
    created_at: datetime | None


class FindingRead(_FromAttrs):
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


class ApprovalRead(_FromAttrs):
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


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    comment: str | None = Field(default=None, max_length=2000)
