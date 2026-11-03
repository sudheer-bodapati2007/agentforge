"""Executes one claimed run to its next stopping point (finished, failed, cancelled or paused)."""

import logging

from app.application.runs.models import ClaimedRun
from app.application.runs.ports import RunRepository, WorkflowEngine
from app.application.runs.service import public_error
from app.application.workflow.routing import wants_database
from app.application.workflow.state import WorkflowState
from app.domain.enums import RunStatus
from app.domain.run import RunCancelledError

logger = logging.getLogger("agentforge.worker")


def initial_state(claim: ClaimedRun) -> WorkflowState:
    run = claim.run
    return WorkflowState(
        run_id=str(run.id),
        project_id=str(run.project_id),
        owner_id=str(claim.owner_id),
        requirements=claim.requirements,
        preferences=claim.preferences,
        require_approval=run.require_approval,
        max_debug_iterations=run.max_debug_iterations,
        max_review_corrections=claim.max_review_corrections,
        database=wants_database(claim.preferences),
        plan_revisions=0,
        test_attempt=0,
        debug_iterations=0,
        debug_history=[],
        memory=[],
        review_cycle=0,
        corrections_applied=0,
        files={},
        usage={"input_tokens": 0, "output_tokens": 0},
    )


class RunProcessor:
    def __init__(self, runs: RunRepository, engine: WorkflowEngine) -> None:
        self._runs = runs
        self._engine = engine

    def process(self, claim: ClaimedRun) -> RunStatus | None:
        run_id = claim.run.id
        try:
            outcome = self._engine.execute(str(run_id), initial_state(claim), claim.resume_payload)
        except RunCancelledError:
            self._runs.finish(run_id, RunStatus.CANCELLED)
            return RunStatus.CANCELLED
        except Exception as exc:  # the run fails; the worker keeps serving others
            logger.exception("run=%s failed", run_id)
            self._runs.finish(run_id, RunStatus.FAILED, error=public_error(exc))
            return RunStatus.FAILED

        if outcome.interrupted:
            self._runs.mark_awaiting_approval(run_id, outcome.interrupt or {})
            return RunStatus.AWAITING_APPROVAL

        status = RunStatus(outcome.state.get("outcome", RunStatus.FAILED.value))
        self._runs.finish(run_id, status, final_report=outcome.state.get("report"))
        return status
