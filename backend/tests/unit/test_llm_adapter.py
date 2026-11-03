"""The LangChain adapter: structured output, token accounting, bounded retries, repair."""

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.application.llm import LLMError, LLMUnavailableError
from app.infrastructure.llm.langchain_llm import LangChainStructuredLLM


class Answer(BaseModel):
    value: int


class StubRunnable:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def invoke(self, messages, config=None):
        self.calls.append((messages, config))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StubChatModel:
    def __init__(self, outcomes):
        self.runnable = StubRunnable(outcomes)
        self.schema = None

    def with_structured_output(self, schema, method, include_raw):
        self.schema = schema
        assert include_raw is True  # needed for token usage
        return self.runnable


def raw(tokens_in=10, tokens_out=5):
    return AIMessage(content="", usage_metadata={"input_tokens": tokens_in, "output_tokens": tokens_out, "total_tokens": tokens_in + tokens_out})


def adapter(outcomes, retries=2):
    model = StubChatModel(outcomes)
    return LangChainStructuredLLM(model, "stub:model", max_retries=retries, backoff_seconds=0, service_backoff_seconds=0), model


def test_structured_result_and_usage():
    llm, model = adapter([{"raw": raw(), "parsed": Answer(value=7), "parsing_error": None}])
    result = llm.generate(task="planner", system="s", user="u", schema=Answer)
    assert result.value.value == 7
    assert (result.usage.input_tokens, result.usage.output_tokens) == (10, 5)
    assert model.runnable.calls[0][1]["tags"] == ["agentforge", "planner"]


def test_invalid_output_gets_one_repair_turn_and_usage_accumulates():
    llm, model = adapter(
        [
            {"raw": raw(10, 5), "parsed": None, "parsing_error": ValueError("missing value")},
            {"raw": raw(12, 6), "parsed": Answer(value=1), "parsing_error": None},
        ]
    )
    result = llm.generate(task="coder", system="s", user="u", schema=Answer)
    assert result.value.value == 1
    assert result.usage.input_tokens == 22
    repair_messages = model.runnable.calls[1][0]
    assert "did not match the required JSON schema" in repair_messages[-1].content


def test_transient_errors_are_retried_then_fail_bounded():
    llm, model = adapter([TimeoutError("slow"), TimeoutError("slow"), TimeoutError("slow")], retries=2)
    with pytest.raises(LLMError, match="after 3 attempts"):
        llm.generate(task="tester", system="s", user="u", schema=Answer)
    assert len(model.runnable.calls) == 3


def test_retries_stop_when_the_time_budget_is_spent():
    ticks = iter([0.0, 400.0, 700.0])  # start, before attempt 2, before attempt 3
    model = StubChatModel([TimeoutError("slow"), TimeoutError("slow"), TimeoutError("slow")])
    llm = LangChainStructuredLLM(model, "stub:model", max_retries=2, backoff_seconds=0, budget_seconds=600, clock=lambda: next(ticks))
    with pytest.raises(LLMError, match="600s time budget after 2 attempt"):
        llm.generate(task="coder", system="s", user="u", schema=Answer)
    assert len(model.runnable.calls) == 2


def test_the_factory_caps_output_length_for_every_provider():
    from app.infrastructure.llm.factory import build_llm
    from tests.conftest import make_settings

    ollama = build_llm(make_settings("sqlite://", llm_provider="ollama", llm_model="m", llm_max_output_tokens=4096))
    assert ollama._model.num_predict == 4096
    assert ollama._budget == 600
    key = "test-" + "key"
    google = build_llm(make_settings("sqlite://", llm_provider="google", llm_model="gemini-x", llm_api_key=key, llm_max_output_tokens=2048))
    assert google._model.max_output_tokens == 2048


def test_thinking_is_only_sent_when_configured():
    from app.infrastructure.llm.factory import build_llm
    from tests.conftest import make_settings

    default = build_llm(make_settings("sqlite://", llm_provider="ollama", llm_model="m"))
    assert default._model.reasoning is None
    off = build_llm(make_settings("sqlite://", llm_provider="ollama", llm_model="m", llm_thinking=False))
    assert off._model.reasoning is False


def test_auth_errors_fail_fast():
    llm, model = adapter([RuntimeError("401 API key not valid")])
    with pytest.raises(LLMUnavailableError, match="rejected"):
        llm.generate(task="planner", system="s", user="u", schema=Answer)
    assert len(model.runnable.calls) == 1


def test_a_persistent_quota_error_means_unavailable_not_a_bad_answer():
    exhausted = RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for metric generate_content_free_tier_requests")
    llm, model = adapter([exhausted, exhausted, exhausted])
    with pytest.raises(LLMUnavailableError, match="quota, rate limit or overload"):
        llm.generate(task="coder", system="s", user="u", schema=Answer)
    assert len(model.runnable.calls) == 3  # retried first: a per-minute limit can clear


def test_provider_overload_is_unavailable_not_a_failed_task():
    overloaded = RuntimeError("GoogleAPIError: 503 UNAVAILABLE. This model is currently experiencing high demand.")
    llm, model = adapter([overloaded, overloaded, overloaded])
    with pytest.raises(LLMUnavailableError, match="not serving"):
        llm.generate(task="tester", system="s", user="u", schema=Answer)
    assert len(model.runnable.calls) == 3


def test_a_quota_message_that_mentions_billing_is_still_retried():
    """Google's 429 text mentions plans and billing; it must not be mistaken for a bad key."""
    quota = RuntimeError("429 RESOURCE_EXHAUSTED: You exceeded your current quota, please check your plan and billing details")
    llm, model = adapter([quota, {"raw": raw(), "parsed": Answer(value=4), "parsing_error": None}])
    assert llm.generate(task="planner", system="s", user="u", schema=Answer).value.value == 4
    assert len(model.runnable.calls) == 2


def test_a_rate_limit_that_clears_is_retried():
    llm, _ = adapter([RuntimeError("429 Too Many Requests"), {"raw": raw(), "parsed": Answer(value=3), "parsing_error": None}])
    assert llm.generate(task="coder", system="s", user="u", schema=Answer).value.value == 3
