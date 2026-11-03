"""Loads benchmark tasks from a dataset directory:

    tasks.json              {"version": 1, "tasks": [{"id", "title", "category",
                                                      "prompt": "tasks/<id>/prompt.md",
                                                      "reference_tests": ["tasks/<id>/test_reference.py"]}]}
    tasks/<id>/prompt.md    the request both systems receive, verbatim
    tasks/<id>/test_*.py    hidden reference tests, placed at tests/<file name> when grading
"""

import json
from pathlib import Path

from app.domain.errors import InvariantViolationError
from app.domain.evaluation import EvaluationTask

SUPPORTED_VERSION = 1


def _read(root: Path, relative: str) -> tuple[Path, str]:
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise InvariantViolationError("dataset", f"{relative!r} is not a file inside {root}")
    return path, path.read_text(encoding="utf-8")


def load_tasks(dataset_dir: Path, only: set[str] | None = None) -> list[EvaluationTask]:
    """Every problem with the dataset is reported as an InvariantViolationError naming it."""
    try:
        return _load(dataset_dir.resolve(), only)
    except (OSError, ValueError) as exc:  # missing files, bad JSON, non-UTF-8 text
        raise InvariantViolationError("dataset", f"cannot read {dataset_dir}: {exc}") from exc
    except (KeyError, TypeError, AttributeError) as exc:
        raise InvariantViolationError("dataset", f"tasks.json is malformed ({exc!r} missing or wrong type)") from exc


def _load(root: Path, only: set[str] | None) -> list[EvaluationTask]:
    data = json.loads((root / "tasks.json").read_text(encoding="utf-8"))
    if data.get("version") != SUPPORTED_VERSION:
        raise InvariantViolationError("version", f"unsupported tasks.json version {data.get('version')!r}")
    tasks: list[EvaluationTask] = []
    for item in data["tasks"]:
        if only and item["id"] not in only:
            continue
        references = {}
        for relative in item["reference_tests"]:
            path, content = _read(root, relative)
            references[f"tests/{path.name}"] = content
        tasks.append(
            EvaluationTask(
                id=item["id"],
                title=item["title"],
                category=item["category"],
                requirements=_read(root, item["prompt"])[1].strip(),
                reference_tests=references,
                database=bool(item.get("database", False)),
            )
        )
    if only and (missing := only - {t.id for t in tasks}):
        raise InvariantViolationError("tasks", f"unknown task id(s): {', '.join(sorted(missing))}")
    ids = [t.id for t in tasks]
    if len(ids) != len(set(ids)):
        raise InvariantViolationError("tasks", "task ids must be unique")
    return tasks
