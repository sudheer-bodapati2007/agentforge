"""Workflow execution records.

These tables are written by the LangGraph workflow (Phase 2+). They exist from the
initial migration so the dashboard can query real (possibly empty) data from day one.
Large payloads (full logs, generated source) live in workspace storage; rows hold
bounded excerpts and references.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.orm.base import Base, TimestampMixin, UTCDateTime, str_enum, utcnow
from app.domain.enums import (
    AgentExecutionStatus,
    AgentRole,
    ApprovalStatus,
    FindingSeverity,
    FindingSource,
    RunStatus,
)

if TYPE_CHECKING:
    from app.infrastructure.persistence.orm.project import ProjectModel


def _run_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )


class WorkflowRunModel(TimestampMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_workflow_runs_project_id_idempotency_key"),
        Index("ix_workflow_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        str_enum(RunStatus), nullable=False, default=RunStatus.QUEUED, index=True
    )
    current_node: Mapped[str | None] = mapped_column(String(64))
    # LangGraph checkpoint thread for resume.
    thread_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    debug_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_debug_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    final_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Who started the run (Supabase user id); ownership is still enforced via the project.
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    require_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_review_corrections: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Job-queue bookkeeping: the claiming worker and its liveness signal.
    worker_id: Mapped[str | None] = mapped_column(String(64))
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Pending human decision to resume the paused graph with (consumed on claim).
    resume_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    llm_model: Mapped[str | None] = mapped_column(String(120))
    demo_model: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    project: Mapped["ProjectModel"] = relationship(back_populates="runs")
    test_results: Mapped[list["TestResultModel"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class AgentExecutionModel(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        UniqueConstraint("run_id", "node", "attempt", name="uq_agent_executions_run_id_node_attempt"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = _run_fk()
    node: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    agent: Mapped[AgentRole | None] = mapped_column(str_enum(AgentRole))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[AgentExecutionStatus] = mapped_column(
        str_enum(AgentExecutionStatus), nullable=False, default=AgentExecutionStatus.PENDING
    )
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class WorkflowEventModel(Base):
    """Append-only event log; the frontend streams these to render live state."""

    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_run_id_id", "run_id", "id"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    node: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("run_id", "path", name="uq_artifacts_run_id_path"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = _run_fk()
    path: Mapped[str] = mapped_column(String(512), nullable=False)  # workspace-relative
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="source")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[AgentRole | None] = mapped_column(str_enum(AgentRole))
    # Bounded by workspace limits (64 KB/file, 600 KB/run). Durable across restarts of
    # stateless hosts; object storage is the scale-out path.
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class TestResultModel(Base):
    """One execution of the test runner. `executed` is False if the suite never ran."""

    __tablename__ = "test_results"
    __test__ = False  # not a pytest test class
    __table_args__ = (UniqueConstraint("run_id", "attempt", name="uq_test_results_run_id_attempt"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = _run_fk()
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    command: Mapped[str] = mapped_column(String(512), nullable=False)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    output_excerpt: Mapped[str | None] = mapped_column(Text)  # bounded tail of runner output
    log_path: Mapped[str | None] = mapped_column(String(512))  # full log in workspace storage
    failures: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    # Projects with a database: migration results and the schema read back afterwards.
    database: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )

    run: Mapped[WorkflowRunModel] = relationship(back_populates="test_results")


class ReviewFindingModel(Base):
    __tablename__ = "review_findings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = _run_fk()
    cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    severity: Mapped[FindingSeverity] = mapped_column(str_enum(FindingSeverity), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512))
    line: Mapped[int | None] = mapped_column(Integer)
    suggestion: Mapped[str | None] = mapped_column(Text)
    source: Mapped[FindingSource] = mapped_column(str_enum(FindingSource), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", "cycle", name="uq_approval_requests_run_id_kind_cycle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = _run_fk()
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ApprovalStatus] = mapped_column(
        str_enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    affected_resources: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    security_notes: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    decision_comment: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
