"""Facts about test failures, computed by AgentForge from the real test output, so the
debugger is told *where* things fail instead of having to read a traceback correctly.

A small model read "tests/test_repository.py:10" in a traceback, could not connect it to
the code (files had no line numbers), and edited app/repository.py three times without
effect. These helpers give it the failing lines' actual code and name the files it keeps
changing for nothing.
"""

import re
from collections import Counter

# A workspace path with a line number as pytest prints it: "tests/test_x.py:10" or "app/x.py:12:".
_FRAME = re.compile(r"(?<![\w/.-])((?:app|tests|db)/[\w./-]+\.(?:py|sql)):(\d+)")
MAX_LOCATIONS = 12


def failure_locations(report: dict, files: dict[str, str]) -> list[dict]:
    """Workspace file lines named by the failures, most frequent first, each with the code on
    that line. Only lines that exist in the current files are returned (nothing invented)."""
    texts = [f"{f.get('message', '')}\n{f.get('file_path') or ''}:{f.get('line') or ''}" for f in report.get("failures") or []]
    texts.append(report.get("output_excerpt") or "")
    counts: Counter[tuple[str, int]] = Counter()
    order: dict[tuple[str, int], int] = {}
    for text in texts:
        for path, raw_line in _FRAME.findall(text):
            key = (path, int(raw_line))
            counts[key] += 1
            order.setdefault(key, len(order))
    locations = []
    for (path, line), count in sorted(counts.items(), key=lambda kv: (-kv[1], order[kv[0]])):
        lines = files.get(path, "").split("\n")
        if path in files and 1 <= line <= len(lines):
            locations.append({"file": path, "line": line, "code": lines[line - 1].strip()[:200], "occurrences": count})
        if len(locations) == MAX_LOCATIONS:
            break
    return locations


def ineffective_files(history: list[dict], current_signature: str) -> dict[str, int]:
    """Files edited by debugging attempts after which the failures did not change, with how
    often. An attempt's effect is visible in the next report (the next attempt's target, or
    the current failures for the latest attempt)."""
    if not history:
        return {}
    after = [entry["failure_signature"] for entry in history[1:]] + [current_signature]
    counts: Counter[str] = Counter()
    for entry, next_signature in zip(history, after, strict=True):
        if entry["failure_signature"] == next_signature:
            counts.update(entry.get("files_changed") or [])
    return dict(counts)


def changed_paths(before: dict[str, str], after: dict[str, str], paths: list[str]) -> list[str]:
    """The paths whose content really changed (a "fix" that rewrites a file identically changes nothing)."""
    return [p for p in paths if before.get(p) != after.get(p)]
