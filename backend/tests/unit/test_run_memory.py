"""Shared run memory: agents write what they assumed, decided and tried; AgentForge writes
facts and verdicts measured from real test runs; later agents read it all."""

from app.application.agents.schemas import DebugPatch, FileContent
from app.application.workflow.memory import MAX_ENTRIES, entry, memory_for_prompt, remember, verdict
from app.domain.testing import TestCaseFailure, TestReport
from tests.fakes import FakeSandbox, ScenarioLLM, failing_report, passing_report
from tests.unit.test_workflow_engine import Harness, initial


def report(passed: int, failed: int, total: int = 5, executed: bool = True, succeeded: bool = False) -> dict:
    return {"executed": executed, "passed": passed, "failed": failed, "errors": 0, "total": total, "succeeded": succeeded}


LOC = [{"file": "tests/test_x.py", "line": 6, "code": "x()", "occurrences": 5}]


def test_verdicts_are_computed_from_the_reports_not_from_the_model():
    assert verdict(report(0, 5), report(5, 0, succeeded=True), LOC, [], ["app/a.py"])[0] == "confirmed"
    assert verdict(report(0, 5), report(3, 2), LOC, LOC, ["app/a.py"])[0] == "partly"
    moved = [{"file": "app/a.py", "line": 9, "code": "y", "occurrences": 5}]
    assert verdict(report(0, 5), report(0, 5), LOC, moved, ["app/a.py"]) == (
        "partly",
        "the failures moved: tests/test_x.py:6 no longer fails, but others do",
    )
    outcome, why = verdict(report(0, 5), report(0, 5), LOC, LOC, ["app/repository.py"])
    assert outcome == "refuted" and "changing app/repository.py did not help" in why
    assert verdict(report(0, 5), report(5, 0, succeeded=True), LOC, [], [])[0] == "refuted"  # nothing was changed
    assert verdict(report(0, 5), report(0, 0, executed=False), LOC, [], ["a"])[0] == "unknown"


def test_fewer_failures_is_not_progress_when_tests_disappear():
    """Real case: a fix broke an import, so 5 failing tests became 1 collection error."""
    outcome, why = verdict(report(0, 5, total=5), {**report(0, 0, total=1), "errors": 1}, LOC, LOC, ["app/repository.py"])
    assert outcome == "regressed" and "no longer collected" in why
    assert verdict(report(3, 2), report(2, 3), LOC, LOC, ["app/a.py"])[0] == "regressed"


def test_memory_is_capped_without_ever_dropping_measurements():
    notes = [entry("code", "coder", "note", f"note {i}") for i in range(MAX_ENTRIES)]
    facts = [entry("run_tests", "agentforge", "fact", f"fact {i}") for i in range(5)]
    kept = remember(notes[:10] + facts + notes[10:], entry("debug", "debugger", "hypothesis", "h"))
    assert len(kept) == MAX_ENTRIES
    assert sum(e["kind"] == "fact" for e in kept) == 5
    assert kept[-1]["kind"] == "hypothesis"
    assert remember([], entry("code", "coder", "note", "   ")) == []  # empty notes are not stored


def test_entries_are_normalised_and_bounded():
    item = entry("plan", "planner", "assumption", "spread\n  over   lines " + "x" * 1000, files=["b", "a", "a"])
    assert item["text"].startswith("spread over lines ") and len(item["text"]) == 400
    assert item["files"] == ["a", "b"]
    line = memory_for_prompt([{**entry("run_tests", "agentforge", "verdict", "same failures", files=["app/a.py"]), "outcome": "refuted"}])
    assert line == ["VERDICT (refuted) by agentforge [app/a.py]: same failures"]


def failing(location: str = "tests/test_api.py:6") -> TestReport:
    return TestReport(
        executed=True, command="pytest", exit_code=1, total=3, passed=0, failed=3,
        failures=[TestCaseFailure(name="t", message=f"{location}: in test\nE   AssertionError")] * 3,
    )


def test_a_refuted_fix_is_recorded_and_the_next_attempt_reads_the_verdict():
    patch = DebugPatch(diagnosis="the store is wrong", root_causes=[], files=[FileContent(path="app/store.py", content="X = 1\n")])
    again = DebugPatch(diagnosis="the store is wrong", root_causes=[], files=[FileContent(path="app/store.py", content="X = 2\n")])
    h = Harness(llm=ScenarioLLM({"debugger": [patch, again]}), sandbox=FakeSandbox([failing()]))
    out = h.run(initial(max_debug=2))

    kinds = [(m["kind"], m.get("outcome")) for m in out.state["memory"]]
    assert ("hypothesis", None) in kinds and ("verdict", "refuted") in kinds
    second_prompt = h.llm.prompts["debugger"][1]
    assert "VERDICT (refuted) by agentforge [app/store.py]: Debug attempt 1 (the store is wrong)" in second_prompt
    assert "<untrusted-run-memory>" in second_prompt
    assert out.state["debug_history"][0]["outcome"] == "refuted"
    assert out.state["report"]["verified"]["memory"] == out.state["memory"]


def test_a_confirmed_fix_and_the_facts_every_agent_reads():
    h = Harness(sandbox=FakeSandbox([failing_report(), passing_report()]))
    out = h.run()
    memory = out.state["memory"]
    assert memory[0]["kind"] == "assumption" and memory[0]["author"] == "planner"
    facts = [m["text"] for m in memory if m["kind"] == "fact"]
    assert facts[0].startswith("Test run 1: 2/3 passed, 1 failed") and facts[1].startswith("Test run 2: 3/3 passed")
    assert [m["outcome"] for m in memory if m["kind"] == "verdict"] == ["confirmed"]
    assert "Shared run memory" in h.llm.prompts["coder"][0]  # the planner's assumptions reach the coder
    assert "Shared run memory" not in h.llm.prompts["planner"][0]
    assert len([e for e in h.journal.events if e["type"] == "memory.added"]) == len(memory)


def test_a_replan_starts_a_fresh_notebook():
    h = Harness()
    first = h.run(initial(require_approval=True))
    ticket = first.interrupt
    resumed = h.engine.execute("11111111-1111-4111-8111-111111111111", None, {"decision": "rejected", "comment": "simpler please"})
    assert ticket and resumed.interrupted
    assumptions = [m for m in resumed.state["memory"] if m["kind"] == "assumption"]
    assert len(assumptions) == len({m["text"] for m in assumptions}), "the rejected plan's notes were dropped, not duplicated"
