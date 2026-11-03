"""Structured outputs for every agent. Kept deliberately flat and small: smaller local
models follow simple schemas far more reliably, and the descriptions double as
instructions in the JSON schema sent to the model."""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]


class PlanTask(BaseModel):
    id: str = Field(description="Short identifier such as T1")
    title: str
    description: str


class ProjectPlan(BaseModel):
    summary: str = Field(description="Two or three sentences describing the software")
    functional_requirements: list[str] = Field(description="What the software must do")
    non_functional_requirements: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, description="Decisions made where requirements are silent")
    open_questions: list[str] = Field(default_factory=list, description="Missing information worth confirming")
    tasks: list[PlanTask] = Field(description="Implementation tasks in order")
    acceptance_criteria: list[str] = Field(description="Testable statements that define done")
    risks: list[str] = Field(default_factory=list)


class Component(BaseModel):
    name: str
    responsibility: str


class PlannedFile(BaseModel):
    path: str = Field(description="Workspace-relative path, e.g. app/models.py")
    purpose: str


class ApiEndpoint(BaseModel):
    method: str
    path: str
    description: str


class DataModel(BaseModel):
    name: str
    fields: list[str] = Field(description="Entries like 'email: str (unique)'")


class ArchitectureSpec(BaseModel):
    summary: str
    components: list[Component]
    technology_decisions: list[str]
    files: list[PlannedFile] = Field(description="Source files to create (tests are written separately)")
    api_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    data_models: list[DataModel] = Field(default_factory=list)
    security_considerations: list[str] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)


class TablePlan(BaseModel):
    name: str
    purpose: str = Field(description="What one row represents")


class SchemaDesign(BaseModel):
    summary: str = Field(description="The data model in two or three sentences")
    tables: list[TablePlan]
    migration_sql: str = Field(
        description="The complete PostgreSQL migration: CREATE TABLE / CREATE INDEX statements, ending each with ';'"
    )
    notes: str = Field(default="", description="Decisions the coder and tester should know about")


class FileContent(BaseModel):
    path: str = Field(description="Workspace-relative path")
    content: str = Field(description="The complete file content, never a fragment or diff")


class CodeChangeSet(BaseModel):
    files: list[FileContent]
    notes: str = Field(default="", description="Brief notes for the next agent")


class TestSuite(BaseModel):
    __test__ = False

    files: list[FileContent] = Field(description="pytest test files, all under tests/")
    notes: str = ""


class DebugPatch(BaseModel):
    diagnosis: str = Field(description="What the test output shows is wrong")
    root_causes: list[str]
    files: list[FileContent] = Field(description="Complete replacements for the files that must change")


class LLMFinding(BaseModel):
    severity: Severity
    category: str = Field(description="e.g. security, correctness, validation, maintainability")
    title: str
    description: str
    file_path: str | None = None
    line: int | None = None
    suggestion: str | None = None


class ReviewReport(BaseModel):
    summary: str
    findings: list[LLMFinding] = Field(default_factory=list)


class Documentation(BaseModel):
    readme: str = Field(description="Complete README.md in Markdown")
