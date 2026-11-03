"""LangGraph implementation of the `WorkflowEngine` port.

The graph topology lives here; node behaviour lives in application/workflow/steps.py and
routing decisions in application/workflow/routing.py (both framework-free).

    plan -> architect -> plan_approval --approved--> [schema, database projects] -> code -> write_tests -> run_tests
                ^              |--rejected+feedback--^ (bounded)          |
                               '--rejected--> report                       v
    run_tests --pass--> review --blocking--> correction_approval --approved--> correct -> run_tests
        |                  '--clean----------------------------------------------> document
        |--fail, retries left--> debug -> run_tests
        '--fail, retry limit / not executed --> document -> report -> END

Approval nodes call `interrupt()`. LangGraph re-executes an interrupted node from its
start on resume, so everything before `interrupt()` must be idempotent: here it only
creates the approval request (a keyed upsert).
"""

import logging
from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.application.runs.ports import EngineOutcome
from app.application.workflow import routing as r
from app.application.workflow.state import WorkflowState
from app.application.workflow.steps import WorkflowSteps

logger = logging.getLogger("agentforge.engine")

RECURSION_LIMIT = 200  # generous upper bound; every loop is bounded by its own counter


def _approval_node(
    request: Callable[[WorkflowState], dict[str, Any]], decision_key: str, feedback_key: str | None = None
) -> Callable[[WorkflowState], dict[str, Any]]:
    def node(state: WorkflowState) -> dict[str, Any]:
        if not state.get("require_approval", True):
            return {decision_key: "auto"}
        ticket = request(state)  # idempotent
        answer = interrupt(ticket) or {}
        decision = "approved" if answer.get("decision") == "approved" else "rejected"
        update: dict[str, Any] = {decision_key: decision}
        if feedback_key:
            comment = (answer.get("comment") or "").strip()
            update[feedback_key] = comment if decision == "rejected" and comment else None
        return update

    return node


def build_graph(steps: WorkflowSteps) -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node(r.PLAN, steps.plan)
    graph.add_node(r.ARCHITECT, steps.architect)
    graph.add_node(r.PLAN_APPROVAL, _approval_node(steps.plan_approval_request, "plan_decision", "plan_feedback"))
    graph.add_node(r.SCHEMA, steps.schema)
    graph.add_node(r.CODE, steps.code)
    graph.add_node(r.WRITE_TESTS, steps.write_tests)
    graph.add_node(r.RUN_TESTS, steps.run_tests)
    graph.add_node(r.DEBUG, steps.debug)
    graph.add_node(r.REVIEW, steps.review)
    graph.add_node(r.CORRECTION_APPROVAL, _approval_node(steps.correction_approval_request, "correction_decision"))
    graph.add_node(r.CORRECT, steps.correct)
    graph.add_node(r.DOCUMENT, steps.document)
    graph.add_node(r.REPORT, steps.report)

    graph.add_edge(START, r.PLAN)
    graph.add_edge(r.PLAN, r.ARCHITECT)
    graph.add_edge(r.ARCHITECT, r.PLAN_APPROVAL)
    graph.add_conditional_edges(r.PLAN_APPROVAL, r.after_plan_approval, [r.SCHEMA, r.CODE, r.PLAN, r.REPORT])
    graph.add_edge(r.SCHEMA, r.CODE)
    graph.add_edge(r.CODE, r.WRITE_TESTS)
    graph.add_edge(r.WRITE_TESTS, r.RUN_TESTS)
    graph.add_conditional_edges(r.RUN_TESTS, r.after_tests, [r.REVIEW, r.DEBUG, r.DOCUMENT])
    graph.add_edge(r.DEBUG, r.RUN_TESTS)
    graph.add_conditional_edges(r.REVIEW, r.after_review, [r.CORRECTION_APPROVAL, r.DOCUMENT])
    graph.add_conditional_edges(r.CORRECTION_APPROVAL, r.after_correction_approval, [r.CORRECT, r.DOCUMENT])
    graph.add_edge(r.CORRECT, r.RUN_TESTS)
    graph.add_edge(r.DOCUMENT, r.REPORT)
    graph.add_edge(r.REPORT, END)
    return graph


class LangGraphWorkflowEngine:
    def __init__(self, *, checkpointer: BaseCheckpointSaver, steps_factory: Callable[[str], WorkflowSteps]) -> None:
        self._checkpointer = checkpointer
        self._steps_factory = steps_factory

    def execute(self, run_id: str, initial_state: WorkflowState, resume: dict[str, Any] | None) -> EngineOutcome:
        compiled = build_graph(self._steps_factory(run_id)).compile(checkpointer=self._checkpointer)
        config = {
            "configurable": {"thread_id": run_id},
            "recursion_limit": RECURSION_LIMIT,
            "run_name": "agentforge.workflow",
            "tags": ["agentforge"],
            "metadata": {"run_id": run_id},
        }
        snapshot = compiled.get_state(config)
        if not snapshot.values:
            payload: Any = initial_state  # fresh run
        elif resume is not None:
            payload = Command(resume=resume)  # human decision for a paused approval
        elif snapshot.next:
            payload = None  # crash recovery / retry: continue from the last checkpoint
        else:
            return EngineOutcome(interrupted=False, state=dict(snapshot.values))  # already finished

        result = compiled.invoke(payload, config)
        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        if interrupts:
            return EngineOutcome(interrupted=True, state=dict(result), interrupt=interrupts[0].value)
        return EngineOutcome(interrupted=False, state=dict(result))
