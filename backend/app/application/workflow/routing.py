"""Conditional edges of the workflow graph, as pure functions of state.

Every loop is bounded by a counter that only increases (debug_iterations,
corrections_applied, plan_revisions), so the graph always reaches a terminal node.
"""

from app.application.workflow.state import WorkflowState
from app.domain.enums import FindingSeverity, FindingSource
from app.domain.review import Finding

MAX_PLAN_REVISIONS = 2

# Node names (shared by the engine and the UI's graph layout)
PLAN = "plan"
ARCHITECT = "architect"
PLAN_APPROVAL = "plan_approval"
SCHEMA = "schema"
CODE = "code"
WRITE_TESTS = "write_tests"
RUN_TESTS = "run_tests"
DEBUG = "debug"
REVIEW = "review"
CORRECTION_APPROVAL = "correction_approval"
CORRECT = "correct"
DOCUMENT = "document"
REPORT = "report"


def finding_from_dict(data: dict) -> Finding:
    return Finding(
        severity=FindingSeverity(data["severity"]),
        category=data["category"],
        title=data["title"],
        description=data["description"],
        source=FindingSource(data["source"]),
        file_path=data.get("file_path"),
        line=data.get("line"),
        suggestion=data.get("suggestion"),
        tool_name=data.get("tool_name"),
    )


def blocking_findings(state: WorkflowState) -> list[dict]:
    return [f for f in state.get("findings") or [] if finding_from_dict(f).blocking]


def wants_database(preferences: dict | None) -> bool:
    """PostgreSQL is the database the sandbox can provide; other choices fall back to SQLite."""
    return "postgres" in str((preferences or {}).get("database") or "").lower()


def after_plan_approval(state: WorkflowState) -> str:
    decision = state.get("plan_decision")
    if decision in ("approved", "auto"):
        return SCHEMA if state.get("database") else CODE
    if state.get("plan_feedback") and state.get("plan_revisions", 0) < MAX_PLAN_REVISIONS:
        return PLAN
    return REPORT  # rejected: finish as cancelled without generating code


def after_tests(state: WorkflowState) -> str:
    report = state.get("test_report") or {}
    if report.get("succeeded"):
        return REVIEW
    if not report.get("executed"):
        return DOCUMENT  # nothing verifiable to debug against
    if state.get("debug_iterations", 0) < state.get("max_debug_iterations", 0):
        return DEBUG
    return DOCUMENT  # retry limit reached: report the remaining failures


def after_review(state: WorkflowState) -> str:
    if blocking_findings(state) and state.get("corrections_applied", 0) < state.get("max_review_corrections", 0):
        return CORRECTION_APPROVAL
    return DOCUMENT


def after_correction_approval(state: WorkflowState) -> str:
    return CORRECT if state.get("correction_decision") in ("approved", "auto") else DOCUMENT


def decide_outcome(state: WorkflowState) -> str:
    if state.get("plan_decision") == "rejected":
        return "cancelled"
    report = state.get("test_report") or {}
    if report.get("succeeded") and not blocking_findings(state):
        return "completed"
    return "partially_completed"
