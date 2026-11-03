"""Use-case tests with an in-memory repository: no database, no HTTP."""

import uuid

import pytest

from app.application.projects import CreateProjectCommand, ProjectService, UpdateProjectCommand
from app.domain.errors import EntityNotFoundError
from app.domain.project import Project, ProjectOverview
from app.domain.user import User

ALICE = User(id=uuid.uuid4(), email="alice@example.com")
MALLORY = User(id=uuid.uuid4(), email="mallory@example.com")


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[uuid.UUID, Project] = {}

    def _owned(self, owner_id, project_id):
        project = self.projects.get(project_id)
        return project if project and project.owner_id == owner_id else None

    def add(self, project: Project) -> None:
        self.projects[project.id] = project

    def get(self, owner_id, project_id):
        return self._owned(owner_id, project_id)

    def get_overview(self, owner_id, project_id):
        project = self._owned(owner_id, project_id)
        return ProjectOverview(project=project) if project else None

    def list_overviews(self, owner_id, *, search, limit, offset):
        matches = [
            p
            for p in self.projects.values()
            if p.owner_id == owner_id and (not search or search.lower() in p.name.lower())
        ]
        return [ProjectOverview(project=p) for p in matches[offset : offset + limit]], len(matches)

    def save(self, project: Project) -> None:
        self.projects[project.id] = project

    def delete(self, owner_id, project_id) -> bool:
        if self._owned(owner_id, project_id) is None:
            return False
        del self.projects[project_id]
        return True


@pytest.fixture
def service() -> ProjectService:
    return ProjectService(InMemoryProjectRepository())


def _create(service: ProjectService, name: str = "Demo", actor: User = ALICE):
    return service.create(actor, CreateProjectCommand(name=name, requirements="r" * 30))


def test_create_assigns_the_actor_as_owner(service):
    created = _create(service)
    assert created.project.owner_id == ALICE.id
    assert service.get(ALICE, created.project.id).project.name == "Demo"


def test_list_trims_search_and_counts(service):
    _create(service, "Alpha API")
    _create(service, "Beta CLI")
    page = service.list(ALICE, search="  alpha ")
    assert page.total == 1
    assert page.items[0].project.name == "Alpha API"


def test_update_with_no_changes_is_a_no_op(service):
    created = _create(service)
    result = service.update(ALICE, created.project.id, UpdateProjectCommand())
    assert result.project.name == "Demo"


def test_missing_project_raises_not_found(service):
    missing = uuid.uuid4()
    with pytest.raises(EntityNotFoundError):
        service.get(ALICE, missing)
    with pytest.raises(EntityNotFoundError):
        service.update(ALICE, missing, UpdateProjectCommand(changes={"name": "x"}))
    with pytest.raises(EntityNotFoundError):
        service.delete(ALICE, missing)


def test_other_users_projects_are_invisible(service):
    project_id = _create(service).project.id
    assert service.list(MALLORY).total == 0
    with pytest.raises(EntityNotFoundError):
        service.get(MALLORY, project_id)
    with pytest.raises(EntityNotFoundError):
        service.update(MALLORY, project_id, UpdateProjectCommand(changes={"name": "pwned"}))
    with pytest.raises(EntityNotFoundError):
        service.delete(MALLORY, project_id)
    assert service.get(ALICE, project_id).project.name == "Demo"
