"""HTTP request/response schemas for projects.

Length limits mirror the domain invariants so clients get field-level 422 errors;
the domain entity still enforces them independently.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.application.projects import CreateProjectCommand, ProjectPage, UpdateProjectCommand
from app.domain import project as rules
from app.domain.enums import ProgrammingLanguage, RunStatus
from app.domain.project import ProjectOverview

ProjectName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=rules.NAME_MAX_LENGTH)
]
Requirements = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=rules.REQUIREMENTS_MIN_LENGTH,
        max_length=rules.REQUIREMENTS_MAX_LENGTH,
    ),
]
ShortOption = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=rules.OPTION_MAX_LENGTH)
]
Constraints = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=rules.CONSTRAINTS_MAX_LENGTH)
]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProjectName
    requirements: Requirements
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    framework: ShortOption | None = None
    database_preference: ShortOption | None = None
    constraints: Constraints | None = None

    def to_command(self) -> CreateProjectCommand:
        return CreateProjectCommand(**self.model_dump())


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProjectName | None = None
    requirements: Requirements | None = None
    language: ProgrammingLanguage | None = None
    framework: ShortOption | None = None
    database_preference: ShortOption | None = None
    constraints: Constraints | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> "ProjectUpdate":
        for field in ("name", "requirements", "language"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"'{field}' cannot be null")
        return self

    def to_command(self) -> UpdateProjectCommand:
        return UpdateProjectCommand(changes=self.model_dump(exclude_unset=True))


class ProjectRead(BaseModel):
    id: uuid.UUID
    name: str
    requirements: str
    language: ProgrammingLanguage
    framework: str | None
    database_preference: str | None
    constraints: str | None
    created_at: datetime
    updated_at: datetime
    run_count: int
    latest_run_status: RunStatus | None

    @classmethod
    def from_overview(cls, overview: ProjectOverview) -> "ProjectRead":
        p = overview.project
        return cls(
            id=p.id,
            name=p.name,
            requirements=p.requirements,
            language=p.language,
            framework=p.framework,
            database_preference=p.database_preference,
            constraints=p.constraints,
            created_at=p.created_at,
            updated_at=p.updated_at,
            run_count=overview.run_count,
            latest_run_status=overview.latest_run_status,
        )


class ProjectList(BaseModel):
    items: list[ProjectRead]
    total: int

    @classmethod
    def from_page(cls, page: ProjectPage) -> "ProjectList":
        return cls(items=[ProjectRead.from_overview(o) for o in page.items], total=page.total)
