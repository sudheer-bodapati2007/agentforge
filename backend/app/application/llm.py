"""LLM port. Agents ask for *structured* output (a Pydantic schema), never free text."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens)

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    value: T
    usage: TokenUsage
    model: str


class LLMError(Exception):
    """The model could not produce a valid response (after the adapter's own retries)."""


class LLMUnavailableError(LLMError):
    """The provider refused service (bad key, no permission, quota or rate limit exhausted).
    Unlike a bad answer, this says nothing about the model's ability: an evaluation must
    stop rather than count it as a failed task."""


class StructuredLLM(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def is_demo(self) -> bool:
        """True for the scripted demo model: output is canned, not AI-generated."""
        ...

    def generate(self, *, task: str, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        """`task` names the calling agent (used for tracing and by the demo model)."""
        ...


@dataclass(frozen=True)
class Pricing:
    input_usd_per_mtok: float
    output_usd_per_mtok: float

    def cost(self, usage: TokenUsage) -> float:
        return (
            usage.input_tokens * self.input_usd_per_mtok + usage.output_tokens * self.output_usd_per_mtok
        ) / 1_000_000
