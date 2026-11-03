"""Code review findings. Each finding records whether a deterministic tool or an LLM produced it."""

from dataclasses import dataclass

from app.domain.enums import FindingSeverity, FindingSource

BLOCKING_SEVERITIES = frozenset({FindingSeverity.CRITICAL, FindingSeverity.HIGH})


@dataclass(frozen=True)
class Finding:
    severity: FindingSeverity
    category: str
    title: str
    description: str
    source: FindingSource
    file_path: str | None = None
    line: int | None = None
    suggestion: str | None = None
    tool_name: str | None = None

    @property
    def blocking(self) -> bool:
        """Tool-verified high/critical issues, or critical issues raised by the LLM reviewer."""
        if self.source is FindingSource.TOOL:
            return self.severity in BLOCKING_SEVERITIES
        return self.severity is FindingSeverity.CRITICAL
