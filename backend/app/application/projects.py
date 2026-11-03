"""Project use cases. Every operation acts on behalf of an authenticated user.

Another user's project is reported as not found (never "forbidden"), so ids of other
people's projects cannot be probed for existence.
"""

import uuid
from dataclasses import dataclass, field

from app.domain.enums import ProgrammingLanguage
from app.domain.errors import EntityNotFoundError
from app.domain.ports import ProjectRepository
from app.domain.project import Project, ProjectOverview
from app.domain.user import User


@dataclass(frozen=True)
class CreateProjectCommand:
    name: str
    requirements: str
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    framework: str | None = None
    database_preference: str | None = None
    constraints: str | None = None


@dataclass(frozen=True)
class UpdateProjectCommand:
    """Only the keys present in `changes` are applied."""

    changes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectPage:
    items: list[ProjectOverview]
    total: int


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def create(self, actor: User, command: CreateProjectCommand) -> ProjectOverview:
        project = Project(
            owner_id=actor.id,
            name=command.name,
            requirements=command.requirements,
            language=command.language,
            framework=command.framework,
            database_preference=command.database_preference,
            constraints=command.constraints,
        )
        self._repository.add(project)
        return ProjectOverview(project=project)

    def list(
        self, actor: User, *, search: str | None = None, limit: int = 50, offset: int = 0
    ) -> ProjectPage:
        search = search.strip() if search else None
        items, total = self._repository.list_overviews(
            actor.id, search=search or None, limit=limit, offset=offset
        )
        return ProjectPage(items=items, total=total)

    def get(self, actor: User, project_id: uuid.UUID) -> ProjectOverview:
        overview = self._repository.get_overview(actor.id, project_id)
        if overview is None:
            raise EntityNotFoundError("Project", project_id)
        return overview

    def update(
        self, actor: User, project_id: uuid.UUID, command: UpdateProjectCommand
    ) -> ProjectOverview:
        project = self._repository.get(actor.id, project_id)
        if project is None:
            raise EntityNotFoundError("Project", project_id)
        if command.changes:
            project.revise(**command.changes)
            self._repository.save(project)
        return self.get(actor, project_id)

    def delete(self, actor: User, project_id: uuid.UUID) -> None:
        if not self._repository.delete(actor.id, project_id):
            raise EntityNotFoundError("Project", project_id)
