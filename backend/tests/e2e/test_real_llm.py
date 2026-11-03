"""End-to-end with a REAL model and the REAL sandbox. Opt-in (slow, needs a model):

    AGENTFORGE_E2E_LLM=ollama:qwen2.5-coder:7b  pytest tests/e2e -s
    AGENTFORGE_E2E_LLM=google:gemini-2.5-flash  LLM_API_KEY=...  pytest tests/e2e -s

The assertions only check what must hold regardless of model quality: every agent produced
valid structured output, tests were really executed, and the outcome follows the results.
"""

import os
import time

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.application.workflow.ports import NullRetriever
from app.application.workflow.steps import WorkflowSteps
from app.infrastructure.config import Settings
from app.infrastructure.llm.factory import build_llm
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox
from app.infrastructure.workflow.langgraph_engine import LangGraphWorkflowEngine
from tests.fakes import InMemoryJournal
from tests.unit.test_workflow_engine import RUN_ID, initial

pytestmark = pytest.mark.llm

SPEC = os.environ.get("AGENTFORGE_E2E_LLM")
if not SPEC:
    pytest.skip("set AGENTFORGE_E2E_LLM=provider:model to run real-model tests", allow_module_level=True)


def test_real_model_builds_and_tests_a_small_library():
    provider, model = SPEC.split(":", 1)
    settings = Settings(
        _env_file=None,
        llm_provider=provider,
        llm_model=model,
        llm_api_key=os.environ.get("LLM_API_KEY"),
        llm_timeout_seconds=600,
    )
    llm = build_llm(settings)
    sandbox = DockerSandbox(image="agentforge-sandbox-python:2", timeout_seconds=120)
    assert sandbox.status().available, sandbox.status().detail
    journal = InMemoryJournal(RUN_ID)
    engine = LangGraphWorkflowEngine(
        checkpointer=InMemorySaver(),
        steps_factory=lambda _: WorkflowSteps(llm=llm, sandbox=sandbox, journal=journal, retriever=NullRetriever()),
    )
    state = initial(max_debug=2)
    state["requirements"] = (
        "Write a Python module app/text_stats.py with a function word_frequencies(text: str) -> dict[str, int] "
        "that lowercases words, ignores punctuation, and raises ValueError for non-string input. "
        "Also add a function top_words(text: str, n: int) -> list[tuple[str, int]] sorted by count then word."
    )
    started = time.monotonic()
    out = engine.execute(RUN_ID, state, None)
    elapsed = time.monotonic() - started

    report = out.state["report"]
    tests = report["verified"]["tests"]
    print(f"\nmodel={llm.model_name} outcome={out.state['outcome']} elapsed={elapsed:.0f}s")
    print(f"test runs={report['verified']['test_runs']} debug={report['verified']['debug_iterations']} "
          f"last={tests['passed']}/{tests['total']} tokens={report['usage']}")
    print("files:", report["verified"]["files"])

    assert tests["executed"] is True, "tests must really run in the sandbox"
    assert tests["total"] > 0
    assert out.state["outcome"] == ("completed" if tests["succeeded"] else "partially_completed")
    assert "app/text_stats.py" in out.state["files"]
