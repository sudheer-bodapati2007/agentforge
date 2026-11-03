"""Workflow paths, end to end through the real LangGraph engine, with fake ports."""

from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.application.agents.prompts import UNCHANGED_FAILURES_NOTE
from app.application.agents.schemas import CodeChangeSet, FileContent
from app.application.llm import LLMError
from app.application.workflow.ports import NullRetriever
from app.application.workflow.steps import WorkflowSteps
from app.domain.enums import FindingSeverity, FindingSource
from app.domain.review import Finding
from app.domain.run import RunCancelledError
from app.domain.testing import TestCaseFailure
from app.infrastructure.workflow.langgraph_engine import LangGraphWorkflowEngine
from tests.fakes import FakeSandbox, InMemoryJournal, ScenarioLLM, failing_report, passing_report

RUN_ID = "11111111-1111-4111-8111-111111111111"


def initial(require_approval=False, max_debug=3, max_corrections=1):
    return {
        "run_id": RUN_ID,
        "project_id": "p",
        "owner_id": "o",
        "requirements": "Build a small task API with tests.",
        "preferences": {"language": "python"},
        "require_approval": require_approval,
        "max_debug_iterations": max_debug,
        "max_review_corrections": max_corrections,
        "plan_revisions": 0,
        "test_attempt": 0,
        "debug_iterations": 0,
        "review_cycle": 0,
        "corrections_applied": 0,
        "files": {},
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


class Harness:
    def __init__(self, llm=None, sandbox=None, journal=None):
        self.llm = llm or ScenarioLLM()
        self.sandbox = sandbox or FakeSandbox()
        self.journal = journal or InMemoryJournal(RUN_ID)
        self.engine = LangGraphWorkflowEngine(
            checkpointer=InMemorySaver(),
            steps_factory=lambda run_id: WorkflowSteps(
                llm=self.llm, sandbox=self.sandbox, journal=self.journal, retriever=NullRetriever()
            ),
        )

    def run(self, state=None, resume=None):
        return self.engine.execute(RUN_ID, state or initial(), resume)


def test_tests_pass_first_time_and_run_completes():
    h = Harness()
    out = h.run()
    assert not out.interrupted
    assert out.state["outcome"] == "completed"
    assert h.journal.finished_nodes() == ["plan", "architect", "code", "write_tests", "run_tests", "review", "document", "report"]
    assert "app/main.py" in h.journal.files and "tests/test_api.py" in h.journal.files
    readme = h.journal.files["README.md"]
    assert "## Verified results" in readme and "3/3 passed" in readme
    # Token usage accumulates over every agent call: 6 model calls x 100 input tokens.
    assert out.state["report"]["usage"]["input_tokens"] == 600
    assert out.state["report"]["verified"]["tests"]["succeeded"] is True


def test_failing_tests_route_to_debugger_and_are_retested():
    h = Harness(sandbox=FakeSandbox([failing_report(), passing_report()]))
    out = h.run()
    assert out.state["outcome"] == "completed"
    assert out.state["debug_iterations"] == 1
    assert len(h.journal.reports) == 2
    assert h.llm.calls.count("debugger") == 1
    # The debugger saw the real failure output.
    assert "assert 1 == 2" in h.llm.prompts["debugger"][0]


def test_retry_limit_stops_safely_with_failures_reported():
    h = Harness(sandbox=FakeSandbox([failing_report()]))
    out = h.run(initial(max_debug=2))
    assert out.state["outcome"] == "partially_completed"
    assert out.state["debug_iterations"] == 2
    assert len(h.journal.reports) == 3  # initial run + one per debugging iteration
    assert "review" not in h.journal.finished_nodes()  # never reviewed unverified code
    limitations = " ".join(out.state["report"]["limitations"])
    assert "failed" in limitations and "2 debugging iteration" in limitations


def test_debugger_remembers_attempts_and_flags_unchanged_failures():
    # The same failure every time: the fixes do nothing.
    h = Harness(sandbox=FakeSandbox([failing_report()]))
    out = h.run(initial(max_debug=3))
    prompts = h.llm.prompts["debugger"]
    first, second = prompts[0], prompts[1]
    assert "previous-attempts" not in first and UNCHANGED_FAILURES_NOTE not in first
    # Later attempts see what was already tried, and that it did not change the failures.
    assert "<untrusted-previous-attempts>" in second and '"attempt": 1' in second
    assert UNCHANGED_FAILURES_NOTE in second
    assert [e["iteration"] for e in out.state["debug_history"]] == [1, 2, 3]
    patches = [e for e in h.journal.events if e["type"] == "debug.patch"]
    assert [p["unchanged_failures"] for p in patches] == [False, True, True]
    # The scripted debugger repeats its diagnosis: each repeat is rejected and re-asked once.
    rejected = [e for e in h.journal.events if e["type"] == "debug.repeat_rejected"]
    assert [e["iteration"] for e in rejected] == [2, 3]
    assert len(prompts) == 5 and "REJECTED: your proposed fix repeats attempt 1" in prompts[2]


def test_debugger_is_told_when_a_fix_changed_the_failures():
    # 2/3 pass, then 2/3 with different failures (progress of a kind), then all pass.
    moved = failing_report(failed=1)
    moved = replace(moved, failures=[TestCaseFailure(name="tests/test_x.py::test_b", message="assert 3 == 4")])
    h = Harness(sandbox=FakeSandbox([failing_report(failed=1), moved, passing_report()]))
    out = h.run(initial(max_debug=3))
    assert out.state["outcome"] == "completed"
    second = h.llm.prompts["debugger"][1]
    assert "failures changed but tests still fail" in second
    assert UNCHANGED_FAILURES_NOTE not in second


def test_a_fix_that_makes_things_worse_is_measured_as_regressed_and_undone():
    # 2/3 pass, then a "fix" drops it to 1/3: regressed, so its changes are reverted.
    h = Harness(sandbox=FakeSandbox([failing_report(failed=1), failing_report(failed=2), passing_report()]))
    out = h.run(initial(max_debug=3))
    assert out.state["outcome"] == "completed"
    assert out.state["debug_history"][0]["outcome"] == "regressed"
    reverted = [e for e in h.journal.events if e["type"] == "debug.reverted"]
    assert reverted and reverted[0]["iteration"] == 1
    second = h.llm.prompts["debugger"][1]
    assert "VERDICT (regressed)" in second and "was reverted because it made things worse" in second
    assert "previous" not in out.state["debug_history"][0], "only the newest attempt keeps an undo snapshot"


def test_unavailable_sandbox_is_reported_honestly():
    h = Harness(sandbox=FakeSandbox(available=False))
    out = h.run()
    assert out.state["outcome"] == "partially_completed"
    assert "debugger" not in h.llm.calls
    assert out.state["report"]["verified"]["tests"]["executed"] is False
    assert "not executed" in h.journal.files["README.md"]


def test_plan_approval_pauses_then_resumes():
    h = Harness()
    first = h.run(initial(require_approval=True))
    assert first.interrupted
    assert first.interrupt["kind"] == "plan"
    assert first.interrupt["affected_resources"] == ["app/models.py", "app/store.py", "app/main.py"]
    assert "code" not in h.journal.finished_nodes()

    second = h.run(resume={"decision": "approved"})
    assert not second.interrupted
    assert second.state["outcome"] == "completed"
    assert h.llm.calls.count("planner") == 1  # approval did not repeat earlier steps
    assert len(h.journal.approvals) == 1  # re-executed gate did not duplicate the request


def test_rejection_with_feedback_replans():
    h = Harness()
    h.run(initial(require_approval=True))
    again = h.run(resume={"decision": "rejected", "comment": "Add pagination to the list endpoint"})
    assert again.interrupted and again.interrupt["cycle"] == 2
    assert "Add pagination to the list endpoint" in h.llm.prompts["planner"][1]
    done = h.run(resume={"decision": "approved"})
    assert done.state["outcome"] == "completed"


def test_rejection_without_feedback_cancels_without_generating_code():
    h = Harness()
    h.run(initial(require_approval=True))
    out = h.run(resume={"decision": "rejected", "comment": ""})
    assert out.state["outcome"] == "cancelled"
    assert "coder" not in h.llm.calls
    assert h.journal.files == {}


def test_blocking_finding_triggers_one_correction_cycle_then_retest():
    secret = Finding(FindingSeverity.HIGH, "security", "S105 hardcoded password", "pw", FindingSource.TOOL, "app/main.py", 3)
    sandbox = FakeSandbox(findings=[secret])

    def fix():
        sandbox.findings = []  # the correction resolves it
        return CodeChangeSet(files=[FileContent(path="app/main.py", content="# fixed\n")])

    h = Harness(llm=ScenarioLLM({"corrector": fix}), sandbox=sandbox)
    out = h.run()
    assert h.llm.calls.count("corrector") == 1
    assert h.journal.finished_nodes().count("run_tests") == 2  # retested after the correction
    assert h.journal.finished_nodes().count("review") == 2
    assert out.state["outcome"] == "completed"


def test_unresolved_blocking_finding_is_bounded_and_reported():
    secret = Finding(FindingSeverity.CRITICAL, "secrets", "Hardcoded key", "k", FindingSource.TOOL, "app/main.py", 1)
    h = Harness(sandbox=FakeSandbox(findings=[secret]))
    out = h.run(initial(max_corrections=1))
    assert h.llm.calls.count("corrector") == 1  # bounded
    assert out.state["outcome"] == "partially_completed"
    assert any("blocking review finding" in item for item in out.state["report"]["limitations"])


def test_unsafe_files_from_the_model_are_rejected():
    bad = CodeChangeSet(
        files=[
            FileContent(path="../escape.py", content="x"),
            FileContent(path="tests/test_sneaky.py", content="x"),  # coder may not write tests
            FileContent(path="app/__init__.py", content=""),
            FileContent(path="app/main.py", content="print('ok')\n"),
        ]
    )
    h = Harness(llm=ScenarioLLM({"coder": bad}))
    h.run()
    assert "../escape.py" not in h.journal.files and "escape.py" not in h.journal.files
    assert "tests/test_sneaky.py" not in h.journal.files
    rejected = [e for e in h.journal.events if e["type"] == "files.rejected"][0]["files"]
    assert any("escape" in item for item in rejected) and any("sneaky" in item for item in rejected)


def test_cancellation_is_observed_at_the_next_step():
    journal = InMemoryJournal(RUN_ID, cancel_after=lambda done: "architect" in done)
    h = Harness(journal=journal)
    with pytest.raises(RunCancelledError):
        h.run()
    assert "code" not in journal.finished_nodes()


def test_crash_recovery_resumes_from_checkpoint_without_repeating_steps():
    llm = ScenarioLLM({"coder": [LLMError("model overloaded"), None]})
    h = Harness(llm=llm)
    with pytest.raises(LLMError):
        h.run()
    assert ("code", "failed", 1) in h.journal.steps
    out = h.run()  # same thread id: continues from the last checkpoint
    assert out.state["outcome"] == "completed"
    assert llm.calls.count("planner") == 1 and llm.calls.count("architect") == 1
    assert llm.calls.count("coder") == 2
