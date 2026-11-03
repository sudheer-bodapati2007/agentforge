"""Typed shared state of a workflow run.

Values are plain JSON-compatible data so the checkpointer can persist them. Reducers
define how concurrent or repeated updates combine: files and approvals merge by key,
token usage accumulates; everything else is last-write-wins.
"""

from typing import Annotated, Any, TypedDict


def merge_dict(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


def add_usage(left: dict | None, right: dict | None) -> dict:
    left, right = left or {}, right or {}
    return {
        "input_tokens": left.get("input_tokens", 0) + right.get("input_tokens", 0),
        "output_tokens": left.get("output_tokens", 0) + right.get("output_tokens", 0),
    }


class WorkflowState(TypedDict, total=False):
    # Inputs (set once at the start)
    run_id: str
    project_id: str
    owner_id: str
    requirements: str
    preferences: dict[str, Any]
    require_approval: bool
    max_debug_iterations: int
    max_review_corrections: int
    # The project has a PostgreSQL database: a schema step runs, and tests get a real database.
    database: bool

    # Planning
    plan: dict[str, Any]
    plan_revisions: int
    plan_feedback: str | None
    plan_decision: str  # approved | rejected | auto
    architecture: dict[str, Any]

    # Workspace snapshot: path -> content (the artifact store is a projection of this)
    files: Annotated[dict[str, str], merge_dict]

    # Testing and debugging
    test_attempt: int
    test_report: dict[str, Any] | None
    debug_iterations: int
    # One entry per debugging attempt (diagnosis, files changed, fingerprint of the
    # failures it targeted) so the next attempt can see what already did not work.
    debug_history: list[dict[str, Any]]
    # Shared run memory: every agent appends short entries (assumptions, decisions, notes,
    # hypotheses) and AgentForge appends facts and verdicts computed from real test runs.
    # Later agents read it. Like debug_history, each node returns a fresh list (idempotent on resume).
    memory: list[dict[str, Any]]

    # Review
    review_cycle: int
    findings: list[dict[str, Any]]
    corrections_applied: int
    correction_decision: str | None

    # Output
    readme_written: bool
    outcome: str
    report: dict[str, Any]
    usage: Annotated[dict[str, int], add_usage]
