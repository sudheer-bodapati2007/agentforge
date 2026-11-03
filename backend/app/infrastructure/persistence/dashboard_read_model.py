"""SQLAlchemy implementation of the `DashboardReadModel` port.

Every aggregate is restricted to one owner's projects; runs and test results are
reached through their project so ownership is enforced in a single place (`_owned`).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.dashboard import DashboardSnapshot, RecentProject, RecentRun
from app.domain.enums import RunStatus
from app.infrastructure.persistence.orm import ProjectModel, TestResultModel, WorkflowRunModel


class SqlAlchemyDashboardReadModel:
    def __init__(self, session: Session) -> None:
        self._session = session

    def snapshot(self, owner_id: uuid.UUID, recent_limit: int) -> DashboardSnapshot:
        s = self._session
        owned = ProjectModel.owner_id == owner_id

        def runs(*columns):
            return select(*columns).join(
                ProjectModel, ProjectModel.id == WorkflowRunModel.project_id
            ).where(owned)

        total_projects = s.scalar(select(func.count(ProjectModel.id)).where(owned)) or 0

        status_counts = {
            RunStatus(status): count
            for status, count in s.execute(
                runs(WorkflowRunModel.status, func.count(WorkflowRunModel.id)).group_by(
                    WorkflowRunModel.status
                )
            )
        }

        suites, passed, total_tests = s.execute(
            select(
                func.count(TestResultModel.id),
                func.coalesce(func.sum(TestResultModel.passed), 0),
                func.coalesce(func.sum(TestResultModel.total), 0),
            )
            .join(WorkflowRunModel, WorkflowRunModel.id == TestResultModel.run_id)
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(owned, TestResultModel.executed.is_(True))
        ).one()

        # Durations are computed in Python to stay portable across PostgreSQL and SQLite.
        durations = [
            (finished - started).total_seconds()
            for started, finished in s.execute(
                runs(WorkflowRunModel.started_at, WorkflowRunModel.finished_at).where(
                    WorkflowRunModel.started_at.is_not(None),
                    WorkflowRunModel.finished_at.is_not(None),
                )
            )
        ]

        total_cost = s.scalar(runs(func.sum(WorkflowRunModel.estimated_cost_usd)))

        recent_runs = [
            RecentRun(
                id=run.id,
                project_id=run.project_id,
                project_name=name,
                status=run.status,
                created_at=run.created_at,
                duration_seconds=(run.finished_at - run.started_at).total_seconds()
                if run.started_at and run.finished_at
                else None,
            )
            for run, name in s.execute(
                runs(WorkflowRunModel, ProjectModel.name)
                .order_by(WorkflowRunModel.created_at.desc())
                .limit(recent_limit)
            )
        ]

        recent_projects = [
            RecentProject(id=p.id, name=p.name, updated_at=p.updated_at)
            for p in s.scalars(
                select(ProjectModel)
                .where(owned)
                .order_by(ProjectModel.updated_at.desc())
                .limit(recent_limit)
            )
        ]

        return DashboardSnapshot(
            total_projects=total_projects,
            run_status_counts=status_counts,
            executed_test_suites=suites,
            tests_passed=passed,
            tests_total=total_tests,
            run_durations_seconds=durations,
            total_estimated_cost_usd=float(total_cost) if total_cost is not None else None,
            recent_runs=recent_runs,
            recent_projects=recent_projects,
        )
