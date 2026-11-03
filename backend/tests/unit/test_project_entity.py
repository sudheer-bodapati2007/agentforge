import uuid

import pytest

from app.domain.enums import ProgrammingLanguage
from app.domain.errors import InvariantViolationError
from app.domain.project import REQUIREMENTS_MIN_LENGTH, Project

VALID_REQUIREMENTS = "x" * REQUIREMENTS_MIN_LENGTH
OWNER = uuid.uuid4()


def test_project_normalises_whitespace_and_blank_optionals():
    project = Project(
        owner_id=OWNER,
        name="  Demo  ",
        requirements=f"  {VALID_REQUIREMENTS}  ",
        framework="   ",
        constraints="",
    )
    assert project.name == "Demo"
    assert project.requirements == VALID_REQUIREMENTS
    assert project.framework is None
    assert project.constraints is None
    assert project.language is ProgrammingLanguage.PYTHON


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "   "),
        ("name", "n" * 121),
        ("requirements", "too short"),
        ("framework", "f" * 81),
    ],
)
def test_project_rejects_invariant_violations(field, value):
    fields = {"name": "Demo", "requirements": VALID_REQUIREMENTS, "owner_id": OWNER, field: value}
    with pytest.raises(InvariantViolationError) as exc:
        Project(**fields)
    assert exc.value.field == field


def test_project_rejects_unknown_language():
    with pytest.raises(ValueError):
        Project(name="Demo", requirements=VALID_REQUIREMENTS, owner_id=OWNER, language="cobol")


def test_revise_applies_valid_changes_and_bumps_updated_at():
    project = Project(name="Demo", requirements=VALID_REQUIREMENTS, owner_id=OWNER)
    before = project.updated_at
    project.revise(name="Renamed", framework="Django")
    assert project.name == "Renamed"
    assert project.framework == "Django"
    assert project.updated_at >= before


def test_revise_is_atomic_when_a_change_is_invalid():
    project = Project(name="Demo", requirements=VALID_REQUIREMENTS, owner_id=OWNER)
    with pytest.raises(InvariantViolationError):
        project.revise(name="Renamed", requirements="short")
    assert project.name == "Demo"


def test_revise_rejects_non_editable_fields():
    project = Project(name="Demo", requirements=VALID_REQUIREMENTS, owner_id=OWNER)
    with pytest.raises(InvariantViolationError):
        project.revise(id="something")


def test_owner_cannot_be_changed_through_revise():
    project = Project(name="Demo", requirements=VALID_REQUIREMENTS, owner_id=OWNER)
    with pytest.raises(InvariantViolationError):
        project.revise(owner_id=uuid.uuid4())
    assert project.owner_id == OWNER
