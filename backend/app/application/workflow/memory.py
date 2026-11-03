"""Shared run memory: one notebook all agents read and write during a run.

Agents add what they assumed, decided, noted or suspected. AgentForge adds what it
*measured*: test-run facts and, after every debugging attempt, a verdict on that attempt's
hypothesis computed from the real re-test (confirmed / partly / refuted). Verdicts are never
the model's opinion of its own fix, so an agent cannot keep insisting on a refuted idea.
"""

from typing import Any

MAX_ENTRIES = 60
MAX_TEXT = 400

# Who may write which kind. FACT and VERDICT come only from AgentForge.
ASSUMPTION, DECISION, NOTE, HYPOTHESIS, FACT, VERDICT = "assumption", "decision", "note", "hypothesis", "fact", "verdict"
MEASURED = frozenset({FACT, VERDICT})
REVERTED = "reverted"  # outcome of a fact entry: a regressing fix was undone


def entry(step: str, author: str, kind: str, text: str, *, files: list[str] | None = None, outcome: str | None = None) -> dict[str, Any]:
    return {
        "step": step,
        "author": author,
        "kind": kind,
        "text": " ".join(str(text).split())[:MAX_TEXT],
        "files": sorted(set(files or []))[:20],
        "outcome": outcome,
    }


def remember(memory: list[dict] | None, *entries: dict) -> list[dict]:
    """A new memory list with the entries appended (empty texts skipped), keeping the newest
    MAX_ENTRIES, but never dropping measured entries in favour of model notes."""
    combined = [*(memory or []), *(e for e in entries if e["text"])]
    if len(combined) <= MAX_ENTRIES:
        return combined
    overflow = len(combined) - MAX_ENTRIES
    kept: list[dict] = []
    for item in combined:
        if overflow and item["kind"] not in MEASURED:
            overflow -= 1
            continue
        kept.append(item)
    return kept[-MAX_ENTRIES:]


def test_fact(attempt: int, report: dict, locations: list[dict]) -> str:
    if not report.get("executed"):
        return f"Test run {attempt}: not executed ({report.get('unavailable_reason')})."
    text = f"Test run {attempt}: {report.get('passed')}/{report.get('total')} passed, {report.get('failed')} failed, {report.get('errors')} errors."
    database = report.get("database") or {}
    failed_migrations = [m.get("file") for m in database.get("migrations", []) if not m.get("ok")]
    if failed_migrations:
        text += f" Migration failed: {', '.join(failed_migrations)}."
    if locations:
        text += " Failing at " + "; ".join(f"{l['file']}:{l['line']} `{l['code']}`" for l in locations[:3]) + "."
    return text


def verdict(before: dict, after: dict, before_locations: list[dict], after_locations: list[dict], files_changed: list[str]) -> tuple[str, str]:
    """(outcome, explanation) for a debugging attempt, from the reports before and after it."""
    if not files_changed:
        return "refuted", "the attempt changed no file, so nothing could improve"
    if after.get("succeeded"):
        return "confirmed", "every test passes after this change"
    if not after.get("executed"):
        return "unknown", "the re-test could not run"
    before_failing = (before.get("failed") or 0) + (before.get("errors") or 0)
    after_failing = (after.get("failed") or 0) + (after.get("errors") or 0)
    # Fewer failures is not progress when tests stopped being collected (e.g. a broken import).
    if (after.get("passed") or 0) < (before.get("passed") or 0) or (after.get("total") or 0) < (before.get("total") or 0):
        return "regressed", (
            f"it made things worse: {after.get('passed')}/{after.get('total')} pass now, "
            f"{before.get('passed')}/{before.get('total')} before"
            + ("; tests are no longer collected (likely a broken import)" if (after.get("total") or 0) < (before.get("total") or 0) else "")
        )
    gone = {(l["file"], l["line"]) for l in before_locations} - {(l["file"], l["line"]) for l in after_locations}
    if after_failing < before_failing or (after.get("passed") or 0) > (before.get("passed") or 0):
        return "partly", f"failing tests went from {before_failing} to {after_failing}"
    if gone:
        return "partly", "the failures moved: " + ", ".join(f"{f}:{n}" for f, n in sorted(gone)[:3]) + " no longer fails, but others do"
    return "refuted", f"the same {after_failing} failure(s) remain at the same places; changing {', '.join(files_changed)} did not help"


def similar(a: str, b: str, threshold: float = 0.7) -> bool:
    """Two diagnoses say essentially the same thing (word overlap, case-insensitive)."""
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= threshold


def memory_for_prompt(memory: list[dict] | None, limit: int = 30) -> list[str]:
    """Compact lines for prompts, newest last."""
    lines = []
    for item in (memory or [])[-limit:]:
        label = item["kind"].upper() + (f" ({item['outcome']})" if item.get("outcome") else "")
        where = f" [{', '.join(item['files'][:4])}]" if item.get("files") else ""
        lines.append(f"{label} by {item['author']}{where}: {item['text']}")
    return lines
