"""Project aggregate: a software requirement that AgentForge workflows run against."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.enums import ProgrammingLanguage, RunStatus
from app.domain.errors import InvariantViolationError

NAME_MAX_LENGTH = 120
REQUIREMENTS_MIN_LENGTH = 20
REQUIREMENTS_MAX_LENGTH = 20_000
OPTION_MAX_LENGTH = 80
CONSTRAINTS_MAX_LENGTH = 5_000


def utcnow() -> datetime:
    return datetime.now(UTC)


def _required_text(field_name: str, value: str, min_length: int, max_length: int) -> str:
    value = value.strip()
    if len(value) < min_length:
        raise InvariantViolationError(field_name, f"must be at least {min_length} characters")
    if len(value) > max_length:
        raise InvariantViolationError(field_name, f"must be at most {max_length} characters")
    return value


def _optional_text(field_name: str, value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > max_length:
        raise InvariantViolationError(field_name, f"must be at most {max_length} characters")
    return value or None


@dataclass
class Project:
    name: str
    requirements: str
    owner_id: uuid.UUID
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    framework: str | None = None
    database_preference: str | None = None
    constraints: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.name = _required_text("name", self.name, 1, NAME_MAX_LENGTH)
        self.requirements = _required_text(
            "requirements", self.requirements, REQUIREMENTS_MIN_LENGTH, REQUIREMENTS_MAX_LENGTH
        )
        self.language = ProgrammingLanguage(self.language)
        self.framework = _optional_text("framework", self.framework, OPTION_MAX_LENGTH)
        self.database_preference = _optional_text(
            "database_preference", self.database_preference, OPTION_MAX_LENGTH
        )
        self.constraints = _optional_text("constraints", self.constraints, CONSTRAINTS_MAX_LENGTH)

    def revise(self, **changes: object) -> None:
        """Apply a partial update, re-validating every touched field."""
        allowed = {
            "name",
            "requirements",
            "language",
            "framework",
            "database_preference",
            "constraints",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise InvariantViolationError(sorted(unknown)[0], "is not an editable field")
        candidate = Project(
            **{
                "owner_id": self.owner_id,
                "name": self.name,
                "requirements": self.requirements,
                "language": self.language,
                "framework": self.framework,
                "database_preference": self.database_preference,
                "constraints": self.constraints,
                **changes,
            }
        )
        for name in allowed:
            setattr(self, name, getattr(candidate, name))
        self.updated_at = utcnow()


@dataclass(frozen=True)
class ProjectOverview:
    """Read model: a project together with a summary of its workflow activity."""

    project: Project
    run_count: int = 0
    latest_run_status: RunStatus | None = None
