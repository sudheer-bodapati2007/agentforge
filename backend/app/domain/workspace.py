"""Rules for files that agents may create in a run's workspace.

Generated paths are untrusted (they come from model output), so every path is
normalised and checked here before anything is stored or executed.
"""

import posixpath
import re
from dataclasses import dataclass

from app.domain.errors import InvariantViolationError

MAX_FILES = 60
MAX_FILE_BYTES = 64_000
MAX_TOTAL_BYTES = 600_000
MAX_PATH_LENGTH = 200

ALLOWED_SUFFIXES = frozenset(
    {".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".json", ".yaml", ".yml", ".sql", ".csv", ".html", ".css"}
)
ALLOWED_DOTFILES = frozenset({".gitignore", ".env.example"})
_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def normalize_path(raw: str) -> str:
    """Return a safe, workspace-relative POSIX path or raise InvariantViolationError."""
    if not isinstance(raw, str) or not raw.strip():
        raise InvariantViolationError("path", "must not be empty")
    candidate = raw.strip().replace("\\", "/")
    if candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate):
        raise InvariantViolationError("path", f"absolute paths are not allowed: {raw!r}")
    normalized = posixpath.normpath(candidate)
    if normalized in (".", "") or normalized.startswith("../") or normalized == "..":
        raise InvariantViolationError("path", f"path escapes the workspace: {raw!r}")
    if len(normalized) > MAX_PATH_LENGTH:
        raise InvariantViolationError("path", "path is too long")
    segments = normalized.split("/")
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment in ALLOWED_DOTFILES and last:
            continue
        if not _SEGMENT.match(segment):
            raise InvariantViolationError("path", f"invalid path segment {segment!r} in {raw!r}")
    name = segments[-1]
    if name not in ALLOWED_DOTFILES:
        suffix = posixpath.splitext(name)[1].lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise InvariantViolationError("path", f"file type {suffix or '(none)'} is not allowed: {raw!r}")
    return normalized


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str

    @classmethod
    def create(cls, path: str, content: str) -> "SourceFile":
        normalized = normalize_path(path)
        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise InvariantViolationError("content", f"{normalized} exceeds {MAX_FILE_BYTES} bytes")
        if "\x00" in content:
            raise InvariantViolationError("content", f"{normalized} contains binary data")
        return cls(path=normalized, content=content)


def merge_files(current: dict[str, str], changes: list[SourceFile]) -> dict[str, str]:
    """Apply validated changes to a snapshot and enforce workspace-wide limits."""
    merged = {**current, **{f.path: f.content for f in changes}}
    if len(merged) > MAX_FILES:
        raise InvariantViolationError("files", f"workspace would exceed {MAX_FILES} files")
    total = sum(len(c.encode("utf-8")) for c in merged.values())
    if total > MAX_TOTAL_BYTES:
        raise InvariantViolationError("files", f"workspace would exceed {MAX_TOTAL_BYTES} bytes")
    return merged
