"""SQLAlchemy implementation of the domain `ProjectRepository` port."""

import uuid

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.domain.enums import RunStatus
from app.domain.project import Project, ProjectOverview
from app.infrastructure.persistence.orm import ProjectModel, WorkflowRunModel

_EDITABLE_FIELDS = (
    "name",
    "requirements",
    "language",
    "framework",
    "database_preference",
    "constraints",
)


def _to_entity(row: ProjectModel) -> Project:
    project = Project(
        name=row.name,
        requirements=row.requirements,
        owner_id=row.owner_id,
        language=row.language,
        framework=row.framework,
        database_preference=row.database_preference,
        constraints=row.constraints,
        id=row.id,
    )
    # Timestamps come from storage, not from entity construction.
    project.created_at = row.created_at
    project.updated_at = row.updated_at
    return project


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlAlchemyProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, project: Project) -> None:
        row = ProjectModel(
            id=project.id,
            owner_id=project.owner_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
            **{name: getattr(project, name) for name in _EDITABLE_FIELDS},
        )
        self._session.add(row)
        self._session.commit()

    def _owned_row(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> ProjectModel | None:
        return self._session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id, ProjectModel.owner_id == owner_id)
        )

    def get(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        row = self._owned_row(owner_id, project_id)
        return _to_entity(row) if row else None

    def get_overview(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> ProjectOverview | None:
        row = self._session.execute(
            self._overview_query().where(
                ProjectModel.id == project_id, ProjectModel.owner_id == owner_id
            )
        ).first()
        return self._to_overview(row) if row else None

    def list_overviews(
        self, owner_id: uuid.UUID, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[ProjectOverview], int]:
        query = self._overview_query().where(ProjectModel.owner_id == owner_id)
        count_query = select(func.count(ProjectModel.id)).where(ProjectModel.owner_id == owner_id)
        if search:
            condition = func.lower(ProjectModel.name).like(
                f"%{_escape_like(search.lower())}%", escape="\\"
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        rows = self._session.execute(
            query.order_by(ProjectModel.updated_at.desc()).limit(limit).offset(offset)
        ).all()
        total = self._session.scalar(count_query) or 0
        return [self._to_overview(row) for row in rows], total

    def save(self, project: Project) -> None:
        row = self._owned_row(project.owner_id, project.id)
        if row is None:
            raise LookupError(f"Project {project.id} does not exist")
        for name in _EDITABLE_FIELDS:
            setattr(row, name, getattr(project, name))
        row.updated_at = project.updated_at
        self._session.commit()

    def delete(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        # Child workflow rows are removed by ON DELETE CASCADE in the database.
        result = self._session.execute(
            delete(ProjectModel).where(ProjectModel.id == project_id, ProjectModel.owner_id == owner_id)
        )
        self._session.commit()
        return result.rowcount > 0

    @staticmethod
    def _overview_query() -> Select:
        run_count = (
            select(func.count(WorkflowRunModel.id))
            .where(WorkflowRunModel.project_id == ProjectModel.id)
            .correlate(ProjectModel)
            .scalar_subquery()
        )
        latest_status = (
            select(WorkflowRunModel.status)
            .where(WorkflowRunModel.project_id == ProjectModel.id)
            .order_by(WorkflowRunModel.created_at.desc())
            .limit(1)
            .correlate(ProjectModel)
            .scalar_subquery()
        )
        return select(ProjectModel, run_count.label("run_count"), latest_status.label("latest"))

    @staticmethod
    def _to_overview(row) -> ProjectOverview:
        model, run_count, latest = row
        return ProjectOverview(
            project=_to_entity(model),
            run_count=run_count or 0,
            latest_run_status=RunStatus(latest) if latest else None,
        )
