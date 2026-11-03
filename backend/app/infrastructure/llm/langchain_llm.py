"""Adapter from a LangChain chat model to the `StructuredLLM` port.

Responsibilities: structured output, token accounting, bounded retries with exponential
backoff for transient failures, one repair round-trip for invalid output, a wall-clock
budget per call, and tracing metadata (picked up by LangSmith when LANGSMITH_TRACING is
enabled). The per-answer output-token cap is set on the chat model by the factory.
"""

import logging
import time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.llm import LLMError, LLMResult, LLMUnavailableError, T, TokenUsage

logger = logging.getLogger("agentforge.llm")

_PERMANENT_HINTS = ("401", "403", "api key", "api_key", "permission", "unauthenticated", "not found", "404")
# The provider is not serving (quota, rate limit, overload): retried with longer waits (these
# often clear), reported as unavailable if they persist, because they say nothing about the model.
_SERVICE_HINTS = (
    "429", "resource_exhausted", "resource exhausted", "quota", "rate limit", "too many requests",
    "503", "unavailable", "overloaded", "high demand",
)
SERVICE_BACKOFF_SECONDS = 15.0


def _usage(raw) -> TokenUsage:
    meta = getattr(raw, "usage_metadata", None) or {}
    return TokenUsage(int(meta.get("input_tokens", 0) or 0), int(meta.get("output_tokens", 0) or 0))


class LangChainStructuredLLM:
    def __init__(
        self,
        chat_model: BaseChatModel,
        model_name: str,
        *,
        max_retries: int = 2,
        method: str = "json_schema",
        backoff_seconds: float = 2.0,
        service_backoff_seconds: float = SERVICE_BACKOFF_SECONDS,
        budget_seconds: float | None = None,
        clock=time.monotonic,
    ) -> None:
        self._model = chat_model
        self._name = model_name
        self._max_retries = max_retries
        self._method = method
        self._backoff = backoff_seconds
        self._service_backoff = service_backoff_seconds
        # Wall-clock budget for one generate() call across all its attempts: a slow or
        # looping model must not turn N retries into N times the timeout.
        self._budget = budget_seconds
        self._clock = clock

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def is_demo(self) -> bool:
        return False

    def generate(self, *, task: str, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        runnable = self._model.with_structured_output(schema, method=self._method, include_raw=True)
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        usage = TokenUsage()
        last_problem = "no response"
        started = self._clock()

        for attempt in range(self._max_retries + 1):
            if attempt and self._budget is not None and self._clock() - started >= self._budget:
                raise LLMError(
                    f"The {task} agent ran out of its {self._budget:.0f}s time budget after {attempt} attempt(s) ({last_problem})"
                )
            try:
                out = runnable.invoke(
                    messages,
                    config={"run_name": f"agentforge.{task}", "tags": ["agentforge", task], "metadata": {"agent": task}},
                )
            except Exception as exc:
                text = str(exc).lower()
                # Checked first: quota messages also mention billing and keys, but may clear.
                not_serving = any(hint in text for hint in _SERVICE_HINTS)
                if not not_serving and any(hint in text for hint in _PERMANENT_HINTS):
                    raise LLMUnavailableError(f"The {task} model call was rejected: {str(exc)[:200]}") from exc
                last_problem = f"{exc.__class__.__name__}: {str(exc)[:200]}"
                if not_serving and attempt == self._max_retries:
                    raise LLMUnavailableError(
                        f"The model provider is not serving requests (quota, rate limit or overload): {last_problem}"
                    ) from exc
                logger.warning("llm task=%s attempt=%d failed: %s", task, attempt + 1, last_problem)
                time.sleep((self._service_backoff if not_serving else self._backoff) * (2**attempt))
                continue

            usage = usage + _usage(out.get("raw"))
            parsed, error = out.get("parsed"), out.get("parsing_error")
            if parsed is not None and error is None:
                return LLMResult(value=parsed, usage=usage, model=self._name)

            last_problem = f"invalid structured output: {str(error)[:300]}"
            logger.warning("llm task=%s attempt=%d %s", task, attempt + 1, last_problem)
            # One repair turn: show the model its own validation error.
            messages = [
                *messages[:2],
                HumanMessage(
                    content=(
                        "Your previous answer did not match the required JSON schema "
                        f"({str(error)[:500]}). Reply again with only a valid JSON object."
                    )
                ),
            ]

        raise LLMError(f"The {task} agent did not get a valid response after {self._max_retries + 1} attempts ({last_problem})")
