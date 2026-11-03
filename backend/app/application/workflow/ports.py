"""Ports the workflow depends on. Implementations live in infrastructure/."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.application.llm import TokenUsage
from app.domain.enums import AgentRole
from app.domain.review import Finding
from app.domain.testing import TestReport


@dataclass(frozen=True)
class SandboxStatus:
    available: bool
    detail: str | None = None


class Sandbox(Protocol):
    """Executes generated code in isolation. Never on the backend host."""

    def status(self) -> SandboxStatus: ...

    def run_tests(self, files: dict[str, str], *, database: bool = False) -> TestReport:
        """With `database`, the tests get a throwaway PostgreSQL database (URL in the
        DATABASE_URL environment variable), the project's migrations are applied first, and
        the report includes the migration results and the resulting schema."""
        ...

    def run_static_analysis(self, files: dict[str, str]) -> list[Finding]:
        """Deterministic analysers (linters, security scanners); empty if unavailable."""
        ...

    def remove_leftovers(self) -> int:
        """Remove containers and networks left behind by a crashed process; returns how many."""
        ...


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    text: str
    score: float
    location: str | None = None


class Retriever(Protocol):
    def retrieve(self, *, owner_id: str, project_id: str, query: str, k: int = 4) -> list[RetrievedChunk]: ...


class NullRetriever:
    def retrieve(self, *, owner_id: str, project_id: str, query: str, k: int = 4) -> list[RetrievedChunk]:
        return []


@dataclass(frozen=True)
class ApprovalTicket:
    id: str
    kind: str
    cycle: int
    status: str
    reason: str
    affected_resources: list[str] = field(default_factory=list)
    security_notes: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class RunJournal(Protocol):
    """Every side effect of one run. All writes are idempotent (keyed upserts), because a
    node that was interrupted or crashed is re-executed when the run resumes."""

    run_id: str

    def is_cancel_requested(self) -> bool: ...

    def step_started(self, node: str, agent: AgentRole | None, attempt: int) -> None: ...

    def step_finished(
        self, node: str, agent: AgentRole | None, attempt: int, summary: str, usage: TokenUsage
    ) -> None: ...

    def step_failed(self, node: str, agent: AgentRole | None, attempt: int, error: str) -> None: ...

    def emit(self, event_type: str, node: str | None = None, **payload: Any) -> None: ...

    def save_files(self, files: dict[str, str], author: AgentRole) -> None: ...

    def save_test_report(self, attempt: int, report: TestReport) -> None: ...

    def save_findings(self, cycle: int, findings: list[Finding]) -> None: ...

    def ensure_approval(
        self,
        *,
        kind: str,
        cycle: int,
        reason: str,
        affected_resources: list[str],
        security_notes: str | None,
        details: dict[str, Any],
    ) -> ApprovalTicket:
        """Create the approval request once; later calls return the existing one."""
        ...
