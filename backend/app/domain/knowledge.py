"""Knowledge base rules (Phase 4): which documents are accepted and how they are chunked.

Documents are user-supplied text that later reaches model prompts, so everything here is
defensive: names are reduced to a safe base name, content must be UTF-8 text within a size
limit, and chunking never loses track of where a chunk came from (file and line range).
"""

import posixpath
import re
from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import InvariantViolationError

MAX_DOCUMENT_BYTES = 400_000  # fits the 1 MB request limit even when JSON escaping doubles it
MAX_DOCUMENTS_PER_PROJECT = 50
# Sparse search scores every chunk of a project per query, so the total is bounded.
MAX_CHUNKS_PER_PROJECT = 5_000
MAX_FILENAME_LENGTH = 120
CHUNK_CHARS = 800
OVERLAP_CHARS = 150

# Letters and digits in any script, plus a few separators; no path or control characters.
_FILENAME = re.compile(r"^[^\W_][\w ().-]*$")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_PY_BLOCK = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")


class DocumentKind(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    PYTHON = "python"


_KINDS = {".md": DocumentKind.MARKDOWN, ".markdown": DocumentKind.MARKDOWN, ".txt": DocumentKind.TEXT,
          ".rst": DocumentKind.TEXT, ".py": DocumentKind.PYTHON}
ALLOWED_EXTENSIONS = tuple(sorted(_KINDS))


def validate_filename(raw: str) -> tuple[str, DocumentKind]:
    """A safe display/base name (any directory part is dropped) and the document kind."""
    if not isinstance(raw, str):
        raise InvariantViolationError("filename", "must be a string")
    name = posixpath.basename(raw.replace("\\", "/").strip())
    if not name or len(name) > MAX_FILENAME_LENGTH or not _FILENAME.match(name):
        raise InvariantViolationError(
            "filename", f"use up to {MAX_FILENAME_LENGTH} letters, digits, spaces, '.', '_', '-', '(' or ')', starting with a letter or digit"
        )
    kind = _KINDS.get(posixpath.splitext(name)[1].lower())
    if kind is None:
        raise InvariantViolationError("filename", f"only {', '.join(ALLOWED_EXTENSIONS)} files are supported")
    return name, kind


def normalize_content(raw: str) -> str:
    """UTF-8 text only, within the size limit, with Unix newlines and no byte-order mark."""
    if not isinstance(raw, str):
        raise InvariantViolationError("content", "must be text")
    text = raw.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text:
        raise InvariantViolationError("content", "binary files are not supported")
    size = len(text.encode("utf-8"))
    if size > MAX_DOCUMENT_BYTES:
        raise InvariantViolationError("content", f"documents are limited to {MAX_DOCUMENT_BYTES // 1000} KB")
    if not text.strip():
        raise InvariantViolationError("content", "the document is empty")
    return text


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    text: str
    start_line: int  # 1-based, inclusive
    end_line: int
    heading: str | None = None  # markdown section path or Python symbol, for context and citations


@dataclass(frozen=True)
class _Block:
    lines: list[tuple[int, str]]  # (line number, text)
    heading: str | None


def _blocks(text: str, kind: DocumentKind) -> list[_Block]:
    """Split at natural boundaries: markdown headings, top-level Python definitions
    (with their decorators), or blank lines between paragraphs."""
    blocks: list[_Block] = []
    current: list[tuple[int, str]] = []
    headings: list[str] = []  # markdown heading stack
    heading: str | None = None

    def flush() -> None:
        if any(line.strip() for _, line in current):
            blocks.append(_Block(list(current), heading))
        current.clear()

    lines = text.split("\n")
    for number, line in enumerate(lines, start=1):
        if kind is DocumentKind.MARKDOWN and (match := _MD_HEADING.match(line)):
            flush()
            level = len(match.group(1))
            headings = [*headings[: level - 1], match.group(2)]
            heading = " > ".join(headings)
        elif kind is DocumentKind.PYTHON and ((match := _PY_BLOCK.match(line)) or line.startswith("@")):
            # A decorator starts the block of the definition below it.
            if not (current and current[-1][1].startswith("@")):
                flush()
            if match:
                heading = match.group(1)
        elif kind is DocumentKind.TEXT and not line.strip():
            current.append((number, line))  # kept, so packed paragraphs stay faithful to the source
            flush()  # paragraph boundary
            continue
        current.append((number, line))
    flush()
    return blocks


def _windows(lines: list[tuple[int, str]], size: int, overlap: int) -> list[list[tuple[int, str]]]:
    """Consecutive line windows of at most `size` characters, each starting with roughly
    `overlap` characters of the previous one. A single over-long line is cut by characters."""
    expanded: list[tuple[int, str]] = []
    for number, line in lines:
        expanded += [(number, line[i : i + size]) for i in range(0, max(len(line), 1), size)]
    windows, start = [], 0
    while start < len(expanded):
        end, used = start, 0
        while end < len(expanded) and (end == start or used + len(expanded[end][1]) + 1 <= size):
            used += len(expanded[end][1]) + 1
            end += 1
        windows.append(expanded[start:end])
        if end >= len(expanded):
            break
        back, carried = end, 0
        while back - 1 > start and carried + len(expanded[back - 1][1]) + 1 <= overlap:
            back -= 1
            carried += len(expanded[back][1]) + 1
        start = back
    return windows


def chunk_document(text: str, kind: DocumentKind, *, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[ChunkDraft]:
    """Structure-aware chunks of at most `size` characters with their line ranges. Small
    neighbouring blocks under the same heading are packed together; large blocks are split
    into overlapping windows so no sentence is lost at a boundary."""
    if size < 100 or not 0 <= overlap < size:
        raise ValueError("chunk size must be >= 100 and overlap smaller than the size")
    groups: list[tuple[list[tuple[int, str]], str | None]] = []
    for block in _blocks(text, kind):
        block_chars = sum(len(line) + 1 for _, line in block.lines)
        if groups:
            last_lines, last_heading = groups[-1]
            last_chars = sum(len(line) + 1 for _, line in last_lines)
            if last_heading == block.heading and last_chars + block_chars <= size:
                last_lines.extend(block.lines)
                continue
        groups.append((list(block.lines), block.heading))

    drafts: list[ChunkDraft] = []
    for lines, heading in groups:
        for window in _windows(lines, size, overlap):
            body = "\n".join(line for _, line in window).strip("\n")
            if body.strip():
                drafts.append(ChunkDraft(len(drafts), body, window[0][0], window[-1][0], heading))
    return drafts
