"""Domain-level errors. The presentation layer maps these to transport responses."""


class DomainError(Exception):
    """Base class for errors raised by domain and application code."""


class EntityNotFoundError(DomainError):
    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(f"{entity} '{identifier}' not found")
        self.entity = entity
        self.identifier = identifier


class ConflictError(DomainError):
    """The request is valid but conflicts with the current state (e.g. already decided)."""


class RateLimitedError(DomainError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class CapabilityUnavailableError(DomainError):
    """A required capability (LLM provider, sandbox) is not configured or reachable."""


class InvariantViolationError(DomainError):
    """A value breaks a business rule (e.g. a project name that is too long)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message
