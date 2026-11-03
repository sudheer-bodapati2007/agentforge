"""Workflow run lifecycle: an explicit state machine with terminal states."""

from app.domain.enums import TERMINAL_RUN_STATUSES, RunStatus
from app.domain.errors import InvariantViolationError

# Every legal transition. Anything else is a bug and is rejected.
ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.AWAITING_APPROVAL,
            RunStatus.COMPLETED,
            RunStatus.PARTIALLY_COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.QUEUED,  # re-queued after a worker crash (resumes from checkpoint)
        }
    ),
    RunStatus.AWAITING_APPROVAL: frozenset({RunStatus.QUEUED, RunStatus.CANCELLED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.PARTIALLY_COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset({RunStatus.QUEUED}),  # explicit retry from the last checkpoint
    RunStatus.CANCELLED: frozenset(),
}


def is_terminal(status: RunStatus) -> bool:
    return status in TERMINAL_RUN_STATUSES


def check_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvariantViolationError("status", f"cannot move a run from {current} to {target}")


class RunCancelledError(Exception):
    """Raised inside the workflow when a cancellation request is observed."""
