"""Test doubles for workflow ports."""

import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from app.application.llm import LLMError, LLMResult, TokenUsage
from app.application.workflow.ports import ApprovalTicket, SandboxStatus
from app.domain.enums import AgentRole
from app.domain.review import Finding
from app.domain.testing import TestCaseFailure, TestReport
from app.infrastructure.llm.scripted import ScriptedLLM


def passing_report(total: int = 3) -> TestReport:
    return TestReport(executed=True, command="pytest", exit_code=0, total=total, passed=total, duration_ms=10)


def failing_report(failed: int = 1, total: int = 3) -> TestReport:
    return TestReport(
        executed=True,
        command="pytest",
        exit_code=1,
        total=total,
        passed=total - failed,
        failed=failed,
        duration_ms=10,
        output_excerpt="E   assert 1 == 2",
        failures=[TestCaseFailure(name="tests/test_x.py::test_a", message="assert 1 == 2")],
    )


class FakeSandbox:
    """Returns queued reports in order (repeating the last one when exhausted)."""

    def __init__(self, reports: list[TestReport] | None = None, findings: list[Finding] | None = None, available: bool = True):
        self.reports = list(reports or [passing_report()])
        self.findings = findings or []
        self.available = available
        self.test_calls: list[dict[str, str]] = []
        self.database_calls: list[bool] = []

    def status(self) -> SandboxStatus:
        return SandboxStatus(self.available, "fake sandbox" if self.available else "Docker is not installed on this host")

    def run_tests(self, files: dict[str, str], *, database: bool = False) -> TestReport:
        self.test_calls.append(dict(files))
        self.database_calls.append(database)
        if not self.available:
            return TestReport(executed=False, command="pytest", unavailable_reason="Docker is not installed on this host")
        return self.reports.pop(0) if len(self.reports) > 1 else self.reports[0]

    def run_static_analysis(self, files: dict[str, str]) -> list[Finding]:
        return list(self.findings) if self.available else []

    def remove_leftovers(self) -> int:
        self.leftovers_removed = True
        return 0


class ScenarioLLM(ScriptedLLM):
    """The scripted demo answers, with per-task overrides (a value, a list consumed in
    order, or a callable) to drive specific workflow paths."""

    def __init__(self, overrides: dict[str, Any] | None = None, usage: TokenUsage = TokenUsage(100, 50)):
        super().__init__()
        self.overrides = overrides or {}
        self.calls: list[str] = []
        self.prompts: dict[str, list[str]] = {}
        self._usage = usage

    @property
    def is_demo(self) -> bool:
        return False

    def generate(self, *, task, system, user, schema):
        self.calls.append(task)
        self.prompts.setdefault(task, []).append(user)
        override = self.overrides.get(task)
        if isinstance(override, list):
            override = override.pop(0) if len(override) > 1 else override[0]
        if isinstance(override, Exception):
            raise override
        if callable(override):
            override = override()
        if override is not None:
            return LLMResult(value=override, usage=self._usage, model="scenario")
        result = super().generate(task=task, system=system, user=user, schema=schema)
        return LLMResult(value=result.value, usage=self._usage, model="scenario")


class InMemoryJournal:
    def __init__(self, run_id: str = "run-1", cancel_after: Callable[[list[str]], bool] | None = None):
        self.run_id = run_id
        self.events: list[dict] = []
        self.steps: list[tuple[str, str, int]] = []
        self.files: dict[str, str] = {}
        self.reports: dict[int, TestReport] = {}
        self.findings: dict[int, list[Finding]] = {}
        self.approvals: dict[tuple[str, int], ApprovalTicket] = {}
        self._cancel_after = cancel_after

    def is_cancel_requested(self) -> bool:
        return bool(self._cancel_after and self._cancel_after([s[0] for s in self.steps if s[1] == "finished"]))

    def step_started(self, node: str, agent: AgentRole | None, attempt: int) -> None:
        self.steps.append((node, "started", attempt))

    def step_finished(self, node, agent, attempt, summary, usage) -> None:
        self.steps.append((node, "finished", attempt))

    def step_failed(self, node, agent, attempt, error) -> None:
        self.steps.append((node, "failed", attempt))

    def emit(self, event_type: str, node: str | None = None, **payload: Any) -> None:
        self.events.append({"type": event_type, "node": node, **payload})

    def save_files(self, files: dict[str, str], author: AgentRole) -> None:
        self.files.update(files)

    def save_test_report(self, attempt: int, report: TestReport) -> None:
        self.reports[attempt] = report

    def save_findings(self, cycle: int, findings: list[Finding]) -> None:
        self.findings[cycle] = findings

    def ensure_approval(self, *, kind, cycle, reason, affected_resources, security_notes, details) -> ApprovalTicket:
        key = (kind, cycle)
        if key not in self.approvals:
            self.approvals[key] = ApprovalTicket(
                id=str(uuid.uuid4()), kind=kind, cycle=cycle, status="pending", reason=reason,
                affected_resources=affected_resources, security_notes=security_notes, details=details,
            )
        return self.approvals[key]

    def finished_nodes(self) -> list[str]:
        return [s[0] for s in self.steps if s[1] == "finished"]


def finding_dict(finding: Finding) -> dict:
    return {**asdict(finding), "severity": finding.severity.value, "source": finding.source.value}


__all__ = [
    "FakeSandbox",
    "InMemoryJournal",
    "LLMError",
    "ScenarioLLM",
    "failing_report",
    "finding_dict",
    "passing_report",
]
