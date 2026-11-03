"""Persistence ports. Infrastructure provides the implementations.

Every read and delete takes the owner's id: there is deliberately no way to fetch
another user's project through this interface.
"""

import uuid
from typing import Protocol

from app.domain.project import Project, ProjectOverview


class ProjectRepository(Protocol):
    def add(self, project: Project) -> None: ...

    def get(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> Project | None: ...

    def get_overview(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> ProjectOverview | None: ...

    def list_overviews(
        self, owner_id: uuid.UUID, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[ProjectOverview], int]: ...

    def save(self, project: Project) -> None: ...

    def delete(self, owner_id: uuid.UUID, project_id: uuid.UUID) -> bool: ...
