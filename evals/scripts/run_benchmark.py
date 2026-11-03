"""Run the Phase 6 benchmark: every task through the multi-agent workflow and the
single-agent baseline, graded by hidden reference tests in the Docker sandbox.

Run from backend/ with the backend's virtualenv (settings come from .env, like the app):

    .venv/Scripts/python ../evals/scripts/run_benchmark.py                   # all tasks, both systems
    .venv/Scripts/python ../evals/scripts/run_benchmark.py --tasks fix_bug,crud --no-db

Results are stored in the evaluation_runs table (unless --no-db) and written to
evals/reports/<benchmark id>.json. Re-running with the same --benchmark-id replaces
that benchmark's rows for the tasks you run (idempotent upserts).
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.application.evaluation.benchmark import GradedAttempt  # noqa: E402
from app.bootstrap import build_benchmark  # noqa: E402
from app.domain.errors import DomainError  # noqa: E402
from app.domain.evaluation import EvaluationResult, SystemKind, summarize, validate_benchmark_id  # noqa: E402
from app.infrastructure.config import Settings  # noqa: E402
from app.domain.workspace import normalize_path  # noqa: E402
from app.infrastructure.evaluation.task_loader import load_tasks  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tasks", help="comma-separated task ids (default: all)")
    parser.add_argument(
        "--systems",
        default=",".join(s.value for s in SystemKind),
        help="comma-separated systems: multi_agent, single_agent (default: both)",
    )
    parser.add_argument("--benchmark-id", default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--dataset", type=Path, default=ROOT / "evals" / "datasets")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "evals" / "reports")
    parser.add_argument("--no-db", action="store_true", help="do not store results in the database")
    return parser.parse_args(argv)


def fmt(value: float | None, pattern: str = "{:.0%}") -> str:
    return "—" if value is None else pattern.format(value)


def print_result(result: EvaluationResult) -> None:
    ref = result.reference_tests
    own = result.own_tests
    print(
        f"  {result.task_id:<17} {result.system.value:<13} "
        f"reference {ref.passed}/{ref.total}{' SOLVED' if result.solved else ''}  "
        f"own {own.passed}/{own.total if own.executed else '—'}  "
        f"debug {result.debug_iterations}  {result.latency_seconds:.0f}s  "
        f"tokens {result.input_tokens + result.output_tokens}"
        + (f"  ERROR: {result.error[:120]}" if result.error else ""),
        flush=True,
    )


def main(argv: list[str] | None = None, *, settings: Settings | None = None, build=build_benchmark) -> int:
    """`settings` and `build` are injectable for tests; the command line uses .env and the real wiring."""
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    settings = settings or Settings()
    only = set(args.tasks.split(",")) if args.tasks else None
    try:
        validate_benchmark_id(args.benchmark_id)  # before any model call: it names the report file
        tasks = load_tasks(args.dataset, only)
        kinds = [SystemKind(value) for value in args.systems.split(",")]
        benchmark = build(settings, persist=not args.no_db)
    except (DomainError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"benchmark {args.benchmark_id}: {len(tasks)} task(s) x {len(kinds)} system(s)", flush=True)
    results: list[EvaluationResult] = []

    def record(result: EvaluationResult) -> None:
        results.append(result)
        print_result(result)

    status, complete = 0, False
    try:
        benchmark.runner.run(
            args.benchmark_id,
            tasks,
            [benchmark.systems[k] for k in kinds],
            on_result=record,
            on_graded=lambda graded: save_attempt(args.report_dir / args.benchmark_id, graded),
        )
        complete = True
    except DomainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        status = 2
    except KeyboardInterrupt:
        print("\ninterrupted: writing the results so far", file=sys.stderr)
        status = 130
    finally:
        benchmark.close()
    if results:
        write_report(args, settings, results, complete)
    return status


def save_attempt(root: Path, graded: GradedAttempt) -> None:
    """<report dir>/<benchmark>/<task>/<system>/: the generated files under files/ and the
    reference test output, so every score can be inspected and explained."""
    folder = root / graded.result.task_id / graded.result.system.value
    for path, content in graded.files.items():
        target = folder / "files" / normalize_path(path)  # model output: re-validated before writing
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    folder.mkdir(parents=True, exist_ok=True)
    report = graded.reference_report
    (folder / "reference_tests.txt").write_text(
        f"{report.passed}/{report.total} passed, {report.failed} failed, {report.errors} errors\n\n"
        + "\n\n".join(f"{f.name}\n{f.message}" for f in report.failures)
        + f"\n\n--- output (tail) ---\n{report.output_excerpt}",
        encoding="utf-8",
    )
    if graded.result.error:
        (folder / "error.txt").write_text(graded.result.error, encoding="utf-8")


def write_report(args: argparse.Namespace, settings: Settings, results: list[EvaluationResult], complete: bool) -> None:
    summaries = summarize(results)
    print("\nsummary" + ("" if complete else " (INCOMPLETE)"))
    for s in summaries:
        print(
            f"  {s.system.value:<13} solved {s.solved}/{s.tasks} ({fmt(s.solve_rate)})  "
            f"reference pass {fmt(s.reference_pass_rate)}  own suite green {fmt(s.own_suite_success_rate)}  "
            f"median {fmt(s.median_latency_seconds, '{:.0f}s')}  tokens {s.total_input_tokens + s.total_output_tokens}  "
            f"errors {s.errors}"
        )

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.report_dir / f"{args.benchmark_id}.json"
    report = {
        "benchmark_id": args.benchmark_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "complete": complete,
        "model": results[0].model_name,
        "settings": {
            "llm_provider": settings.llm_provider,
            "llm_temperature": settings.llm_temperature,
            "max_debug_iterations": settings.max_debug_iterations,
            "max_review_corrections": settings.max_review_corrections,
        },
        "summaries": [asdict(s) for s in summaries],
        "results": [asdict(r) | {"solved": r.solved} for r in results],
    }
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nreport: {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
