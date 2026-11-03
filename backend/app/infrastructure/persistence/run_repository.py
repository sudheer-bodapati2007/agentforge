"""SQLAlchemy implementation of the `RunRepository` port.

The queue is the `workflow_runs` table itself. Claims use compare-and-set
(`UPDATE ... WHERE id = ? AND status = 'queued'`), which is race-safe on PostgreSQL and
SQLite alike: when two workers race for a run, exactly one update affects a row.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

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
from app.application.runs.service import run_preferences
from app.infrastructure.persistence.mapping import to_view
from app.domain.enums import ApprovalStatus, RunStatus
from app.domain.errors import ConflictError, EntityNotFoundError
from app.domain.run import check_transition
from app.infrastructure.persistence.orm import (
    AgentExecutionModel,
    ApprovalRequestModel,
    ArtifactModel,
    ProjectModel,
    ReviewFindingModel,
    TestResultModel,
    WorkflowEventModel,
    WorkflowRunModel,
)

ACTIVE_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL)


def utcnow() -> datetime:
    return datetime.now(UTC)


def run_view(run: WorkflowRunModel, project_name: str) -> RunView:
    return to_view(RunView, run, project_name=project_name)


def add_event(session: Session, run_id: uuid.UUID, event_type: str, node: str | None = None, **payload: Any) -> None:
    session.add(WorkflowEventModel(run_id=run_id, type=event_type, node=node, payload=payload))


class SqlAlchemyRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ------------------------------------------------------------------ helpers

    def _owned_query(self, owner_id: uuid.UUID):
        return (
            select(WorkflowRunModel, ProjectModel.name)
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(ProjectModel.owner_id == owner_id)
        )

    def _view(self, run_id: uuid.UUID) -> RunView:
        row = self._s.execute(
            select(WorkflowRunModel, ProjectModel.name)
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(WorkflowRunModel.id == run_id)
        ).first()
        if row is None:
            raise EntityNotFoundError("Run", run_id)
        return run_view(*row)

    def _transition(self, run: WorkflowRunModel, target: RunStatus) -> None:
        check_transition(RunStatus(run.status), target)
        run.status = target

    # ------------------------------------------------------------------ commands

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
    ) -> RunView:
        run = WorkflowRunModel(
            project_id=project_id,
            requested_by=requested_by,
            status=RunStatus.QUEUED,
            require_approval=require_approval,
            max_debug_iterations=max_debug_iterations,
            max_review_corrections=max_review_corrections,
            idempotency_key=idempotency_key,
            llm_model=llm_model,
            demo_model=demo_model,
        )
        self._s.add(run)
        self._s.flush()
        run.thread_id = str(run.id)
        add_event(self._s, run.id, "run.queued", require_approval=require_approval, model=llm_model)
        self._s.commit()
        return self._view(run.id)

    def find_by_idempotency_key(self, owner_id: uuid.UUID, project_id: uuid.UUID, key: str) -> RunView | None:
        row = self._s.execute(
            self._owned_query(owner_id).where(
                WorkflowRunModel.project_id == project_id, WorkflowRunModel.idempotency_key == key
            )
        ).first()
        return run_view(*row) if row else None

    def get_for_owner(self, owner_id: uuid.UUID, run_id: uuid.UUID) -> RunView | None:
        row = self._s.execute(self._owned_query(owner_id).where(WorkflowRunModel.id == run_id)).first()
        return run_view(*row) if row else None

    def list_for_owner(
        self, owner_id: uuid.UUID, *, project_id: uuid.UUID | None, status: RunStatus | None, limit: int, offset: int
    ) -> tuple[list[RunView], int]:
        query = self._owned_query(owner_id)
        count = (
            select(func.count(WorkflowRunModel.id))
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(ProjectModel.owner_id == owner_id)
        )
        if project_id:
            query = query.where(WorkflowRunModel.project_id == project_id)
            count = count.where(WorkflowRunModel.project_id == project_id)
        if status:
            query = query.where(WorkflowRunModel.status == status)
            count = count.where(WorkflowRunModel.status == status)
        rows = self._s.execute(query.order_by(WorkflowRunModel.created_at.desc()).limit(limit).offset(offset)).all()
        return [run_view(*r) for r in rows], self._s.scalar(count) or 0

    def count_active_for_owner(self, owner_id: uuid.UUID) -> int:
        return self._s.scalar(
            select(func.count(WorkflowRunModel.id))
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(ProjectModel.owner_id == owner_id, WorkflowRunModel.status.in_(ACTIVE_STATUSES))
        ) or 0

    def count_created_since(self, owner_id: uuid.UUID, since: datetime) -> int:
        return self._s.scalar(
            select(func.count(WorkflowRunModel.id))
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(ProjectModel.owner_id == owner_id, WorkflowRunModel.created_at >= since)
        ) or 0

    def request_cancel(self, run_id: uuid.UUID) -> RunView:
        run = self._s.get(WorkflowRunModel, run_id)
        if run is None:
            raise EntityNotFoundError("Run", run_id)
        status = RunStatus(run.status)
        if status in (RunStatus.QUEUED, RunStatus.AWAITING_APPROVAL):
            # Nothing is executing: cancel immediately.
            self._transition(run, RunStatus.CANCELLED)
            run.finished_at = utcnow()
            run.resume_payload = None
            add_event(self._s, run.id, "run.cancelled")
        else:
            # A worker owns it: the workflow observes the flag at its next step boundary.
            run.cancel_requested = True
            add_event(self._s, run.id, "run.cancel_requested")
        self._s.commit()
        return self._view(run_id)

    def decide_approval(
        self, run_id: uuid.UUID, approval_id: uuid.UUID, status: ApprovalStatus, comment: str | None
    ) -> ApprovalView:
        # Compare-and-set so two concurrent decisions cannot both succeed.
        result = self._s.execute(
            update(ApprovalRequestModel)
            .where(
                ApprovalRequestModel.id == approval_id,
                ApprovalRequestModel.run_id == run_id,
                ApprovalRequestModel.status == ApprovalStatus.PENDING,
            )
            .values(status=status, decision_comment=comment, decided_at=utcnow())
        )
        if result.rowcount != 1:
            self._s.rollback()
            raise ConflictError("This approval request was already decided")
        row = self._s.get(ApprovalRequestModel, approval_id)
        add_event(self._s, run_id, "approval.decided", kind=row.kind, decision=status.value, comment=comment)
        self._s.commit()
        return _approval_view(row)

    def requeue(self, run_id: uuid.UUID, resume_payload: dict[str, Any] | None) -> RunView:
        run = self._s.get(WorkflowRunModel, run_id)
        if run is None:
            raise EntityNotFoundError("Run", run_id)
        self._transition(run, RunStatus.QUEUED)
        run.finished_at = None
        run.error = None
        run.resume_payload = resume_payload
        add_event(self._s, run.id, "run.queued", resumed=True)
        self._s.commit()
        return self._view(run_id)

    # ------------------------------------------------------------------ queue

    def claim_next(self, worker_id: str) -> ClaimedRun | None:
        candidates = self._s.execute(
            select(WorkflowRunModel.id, WorkflowRunModel.started_at)
            .where(WorkflowRunModel.status == RunStatus.QUEUED)
            .order_by(WorkflowRunModel.created_at)
            .limit(5)
        ).all()
        for run_id, started_at in candidates:
            now = utcnow()
            claimed = self._s.execute(
                update(WorkflowRunModel)
                .where(WorkflowRunModel.id == run_id, WorkflowRunModel.status == RunStatus.QUEUED)
                .values(
                    status=RunStatus.RUNNING,
                    worker_id=worker_id,
                    heartbeat_at=now,
                    started_at=func.coalesce(WorkflowRunModel.started_at, now),
                )
            ).rowcount
            if claimed != 1:
                self._s.rollback()
                continue  # another worker won this one
            run = self._s.get(WorkflowRunModel, run_id)
            self._s.refresh(run)
            project = self._s.get(ProjectModel, run.project_id)
            resume = run.resume_payload
            run.resume_payload = None  # consumed exactly once
            add_event(self._s, run.id, "run.started", worker=worker_id, resumed=started_at is not None)
            self._s.commit()
            return ClaimedRun(
                run=run_view(run, project.name),
                owner_id=project.owner_id,
                requirements=project.requirements,
                preferences=run_preferences(
                    project.language.value if hasattr(project.language, "value") else str(project.language),
                    project.framework,
                    project.database_preference,
                    project.constraints,
                ),
                max_review_corrections=run.max_review_corrections,
                resume_payload=resume,
                is_continuation=started_at is not None,
            )
        return None

    def heartbeat(self, run_id: uuid.UUID, worker_id: str) -> None:
        self._s.execute(
            update(WorkflowRunModel)
            .where(WorkflowRunModel.id == run_id, WorkflowRunModel.worker_id == worker_id)
            .values(heartbeat_at=utcnow())
        )
        self._s.commit()

    def mark_awaiting_approval(self, run_id: uuid.UUID, ticket: dict[str, Any]) -> None:
        run = self._s.get(WorkflowRunModel, run_id)
        self._transition(run, RunStatus.AWAITING_APPROVAL)
        run.worker_id = None
        run.current_node = ticket.get("kind") and f"{ticket['kind']}_approval"
        add_event(self._s, run_id, "run.awaiting_approval", run.current_node, **ticket)
        self._s.commit()

    def finish(
        self,
        run_id: uuid.UUID,
        status: RunStatus,
        *,
        error: str | None = None,
        final_report: dict[str, Any] | None = None,
    ) -> None:
        run = self._s.get(WorkflowRunModel, run_id)
        self._transition(run, status)
        run.finished_at = utcnow()
        run.worker_id = None
        run.error = error
        run.cancel_requested = False
        if final_report is not None:
            run.final_report = final_report
            run.estimated_cost_usd = (final_report.get("usage") or {}).get("estimated_cost_usd")
        # Token totals are the sum of every agent execution (including retried steps).
        tokens_in, tokens_out = self._s.execute(
            select(
                func.coalesce(func.sum(AgentExecutionModel.input_tokens), 0),
                func.coalesce(func.sum(AgentExecutionModel.output_tokens), 0),
            ).where(AgentExecutionModel.run_id == run_id)
        ).one()
        run.input_tokens, run.output_tokens = int(tokens_in), int(tokens_out)
        add_event(self._s, run_id, "run.finished", status=status.value, error=error)
        self._s.commit()

    def requeue_stale(self, older_than: datetime) -> int:
        stale = self._s.scalars(
            select(WorkflowRunModel).where(
                WorkflowRunModel.status == RunStatus.RUNNING, WorkflowRunModel.heartbeat_at < older_than
            )
        ).all()
        for run in stale:
            run.status = RunStatus.QUEUED
            run.worker_id = None
            add_event(self._s, run.id, "run.recovered", reason="worker stopped responding; resuming from checkpoint")
        self._s.commit()
        return len(stale)

    # ------------------------------------------------------------------ reads

    def _rows(self, model, run_id: uuid.UUID, *order_by):
        return self._s.scalars(select(model).where(model.run_id == run_id).order_by(*order_by)).all()

    def events_after(self, run_id: uuid.UUID, after_id: int, limit: int) -> list[EventView]:
        rows = self._s.scalars(
            select(WorkflowEventModel)
            .where(WorkflowEventModel.run_id == run_id, WorkflowEventModel.id > after_id)
            .order_by(WorkflowEventModel.id)
            .limit(limit)
        ).all()
        return [to_view(EventView, e) for e in rows]

    def agent_executions(self, run_id: uuid.UUID) -> list[AgentExecutionView]:
        rows = self._rows(AgentExecutionModel, run_id, AgentExecutionModel.started_at, AgentExecutionModel.attempt)
        return [to_view(AgentExecutionView, r) for r in rows]

    def artifacts(self, run_id: uuid.UUID) -> list[ArtifactView]:
        return [to_view(ArtifactView, r) for r in self._rows(ArtifactModel, run_id, ArtifactModel.path)]

    def artifact_contents(self, run_id: uuid.UUID) -> dict[str, str]:
        rows = self._s.execute(
            select(ArtifactModel.path, ArtifactModel.content).where(ArtifactModel.run_id == run_id)
        ).all()
        return dict(rows)

    def test_results(self, run_id: uuid.UUID) -> list[TestResultView]:
        rows = self._rows(TestResultModel, run_id, TestResultModel.attempt)
        return [to_view(TestResultView, r, failures=r.failures or []) for r in rows]

    def findings(self, run_id: uuid.UUID) -> list[FindingView]:
        rows = self._rows(ReviewFindingModel, run_id, ReviewFindingModel.cycle, ReviewFindingModel.created_at)
        return [to_view(FindingView, r) for r in rows]

    def approvals(self, run_id: uuid.UUID) -> list[ApprovalView]:
        return [_approval_view(r) for r in self._rows(ApprovalRequestModel, run_id, ApprovalRequestModel.requested_at)]


def _approval_view(r: ApprovalRequestModel) -> ApprovalView:
    return to_view(ApprovalView, r, affected_resources=r.affected_resources or [], details=r.details or {})
