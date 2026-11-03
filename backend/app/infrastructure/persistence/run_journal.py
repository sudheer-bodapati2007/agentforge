"""SQLAlchemy implementation of the `RunJournal` port.

Every write is an idempotent, keyed upsert: (run, node, attempt) for agent executions,
(run, path) for artifacts, (run, attempt) for test results, (run, cycle) for findings,
(run, kind, cycle) for approvals. Re-executing a step after a crash or an approval
resume therefore never duplicates records.
"""

import hashlib
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.llm import TokenUsage
from app.application.workflow.ports import ApprovalTicket
from app.domain.enums import AgentExecutionStatus, AgentRole, ApprovalStatus
from app.domain.review import Finding
from app.domain.testing import TestReport
from app.infrastructure.persistence.orm import (
    AgentExecutionModel,
    ApprovalRequestModel,
    ArtifactModel,
    ReviewFindingModel,
    TestResultModel,
    WorkflowRunModel,
)
from app.infrastructure.persistence.run_repository import add_event

MAX_EXCERPT_CHARS = 64_000


def utcnow() -> datetime:
    return datetime.now(UTC)


def _kind_for(path: str) -> str:
    if path.startswith("tests/"):
        return "test"
    if path.lower().endswith(".md"):
        return "doc"
    return "source"


class SqlAlchemyRunJournal:
    def __init__(self, session_factory: sessionmaker[Session], run_id: str) -> None:
        self._session_factory = session_factory
        self.run_id = run_id
        self._run_uuid = uuid.UUID(run_id)

    def _session(self) -> Session:
        return self._session_factory()

    # ------------------------------------------------------------------ control

    def is_cancel_requested(self) -> bool:
        with self._session() as s:
            return bool(s.scalar(select(WorkflowRunModel.cancel_requested).where(WorkflowRunModel.id == self._run_uuid)))

    # ------------------------------------------------------------------ steps

    def _execution(self, s: Session, node: str, attempt: int) -> AgentExecutionModel:
        row = s.scalar(
            select(AgentExecutionModel).where(
                AgentExecutionModel.run_id == self._run_uuid,
                AgentExecutionModel.node == node,
                AgentExecutionModel.attempt == attempt,
            )
        )
        if row is None:
            row = AgentExecutionModel(run_id=self._run_uuid, node=node, attempt=attempt)
            s.add(row)
        return row

    def step_started(self, node: str, agent: AgentRole | None, attempt: int) -> None:
        with self._session() as s:
            row = self._execution(s, node, attempt)
            row.agent = agent
            row.status = AgentExecutionStatus.RUNNING
            row.started_at = utcnow()
            row.finished_at = None
            row.error = None
            run = s.get(WorkflowRunModel, self._run_uuid)
            run.current_node = node
            run.heartbeat_at = utcnow()
            add_event(s, self._run_uuid, "node.started", node, agent=agent.value if agent else None, attempt=attempt)
            s.commit()

    def step_finished(self, node: str, agent: AgentRole | None, attempt: int, summary: str, usage: TokenUsage) -> None:
        with self._session() as s:
            row = self._execution(s, node, attempt)
            row.status = AgentExecutionStatus.COMPLETED
            row.summary = summary
            row.input_tokens = usage.input_tokens
            row.output_tokens = usage.output_tokens
            row.finished_at = utcnow()
            run = s.get(WorkflowRunModel, self._run_uuid)
            if node == "debug":
                run.debug_iterations = max(run.debug_iterations, attempt)
            add_event(
                s,
                self._run_uuid,
                "node.completed",
                node,
                agent=agent.value if agent else None,
                attempt=attempt,
                summary=summary,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
            s.commit()

    def step_failed(self, node: str, agent: AgentRole | None, attempt: int, error: str) -> None:
        with self._session() as s:
            row = self._execution(s, node, attempt)
            row.status = AgentExecutionStatus.FAILED
            row.error = error
            row.finished_at = utcnow()
            add_event(s, self._run_uuid, "node.failed", node, agent=agent.value if agent else None, attempt=attempt, error=error)
            s.commit()

    def emit(self, event_type: str, node: str | None = None, **payload: Any) -> None:
        with self._session() as s:
            if node is None:
                node = s.scalar(select(WorkflowRunModel.current_node).where(WorkflowRunModel.id == self._run_uuid))
            add_event(s, self._run_uuid, event_type, node, **payload)
            s.commit()

    # ------------------------------------------------------------------ outputs

    def save_files(self, files: dict[str, str], author: AgentRole) -> None:
        with self._session() as s:
            existing = {
                a.path: a
                for a in s.scalars(
                    select(ArtifactModel).where(ArtifactModel.run_id == self._run_uuid, ArtifactModel.path.in_(list(files)))
                )
            }
            for path, content in files.items():
                data = content.encode("utf-8")
                row = existing.get(path) or ArtifactModel(run_id=self._run_uuid, path=path)
                row.content = content
                row.sha256 = hashlib.sha256(data).hexdigest()
                row.size_bytes = len(data)
                row.kind = _kind_for(path)
                row.created_by = row.created_by or author
                row.updated_at = utcnow()
                s.add(row)
            s.commit()

    def save_test_report(self, attempt: int, report: TestReport) -> None:
        with self._session() as s:
            row = s.scalar(
                select(TestResultModel).where(TestResultModel.run_id == self._run_uuid, TestResultModel.attempt == attempt)
            ) or TestResultModel(run_id=self._run_uuid, attempt=attempt)
            row.command = report.command[:512]
            row.executed = report.executed
            row.exit_code = report.exit_code
            row.total, row.passed, row.failed = report.total, report.passed, report.failed
            row.errors, row.skipped = report.errors, report.skipped
            row.duration_ms = report.duration_ms
            row.output_excerpt = report.output_excerpt[-MAX_EXCERPT_CHARS:]
            row.failures = [asdict(f) for f in report.failures[:50]]
            row.unavailable_reason = report.unavailable_reason
            row.database = asdict(report.database) if report.database else None
            s.add(row)
            s.commit()

    def save_findings(self, cycle: int, findings: list[Finding]) -> None:
        with self._session() as s:
            s.execute(
                delete(ReviewFindingModel).where(
                    ReviewFindingModel.run_id == self._run_uuid, ReviewFindingModel.cycle == cycle
                )
            )
            for f in findings[:200]:
                s.add(
                    ReviewFindingModel(
                        run_id=self._run_uuid,
                        cycle=cycle,
                        severity=f.severity,
                        category=f.category[:64],
                        title=f.title[:256],
                        description=f.description,
                        file_path=f.file_path,
                        line=f.line,
                        suggestion=f.suggestion,
                        source=f.source,
                        tool_name=f.tool_name,
                    )
                )
            s.commit()

    def ensure_approval(
        self,
        *,
        kind: str,
        cycle: int,
        reason: str,
        affected_resources: list[str],
        security_notes: str | None,
        details: dict[str, Any],
    ) -> ApprovalTicket:
        with self._session() as s:
            row = s.scalar(
                select(ApprovalRequestModel).where(
                    ApprovalRequestModel.run_id == self._run_uuid,
                    ApprovalRequestModel.kind == kind,
                    ApprovalRequestModel.cycle == cycle,
                )
            )
            if row is None:
                row = ApprovalRequestModel(
                    run_id=self._run_uuid,
                    kind=kind,
                    cycle=cycle,
                    status=ApprovalStatus.PENDING,
                    reason=reason,
                    affected_resources=affected_resources[:100],
                    security_notes=security_notes,
                    details=details,
                )
                s.add(row)
                s.flush()
                add_event(s, self._run_uuid, "approval.requested", f"{kind}_approval", kind=kind, approval_id=str(row.id))
                s.commit()
            return ApprovalTicket(
                id=str(row.id),
                kind=row.kind,
                cycle=row.cycle,
                status=ApprovalStatus(row.status).value,
                reason=row.reason,
                affected_resources=row.affected_resources or [],
                security_notes=row.security_notes,
                details=row.details or {},
            )
