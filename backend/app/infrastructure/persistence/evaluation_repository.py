"""SQLAlchemy implementation of the `EvaluationRepository` port."""

from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.evaluation.ports import StoredBenchmark
from app.domain.evaluation import EvaluationResult, TestTally
from app.infrastructure.persistence.orm import EvaluationRunModel

# Result fields stored as same-named columns; the two test tallies are flattened with a prefix.
_PLAIN = (
    "benchmark_id", "task_id", "task_title", "category", "system", "model_name", "demo_model",
    "debug_iterations", "test_runs", "findings_total", "blocking_findings", "latency_seconds",
    "input_tokens", "output_tokens", "estimated_cost_usd", "human_interventions", "error",
)
_TALLIES = {"own_tests": "own_tests", "reference_tests": "reference"}
_TALLY_FIELDS = ("executed", "passed", "total", "errors")


def _to_columns(result: EvaluationResult) -> dict:
    values = {name: getattr(result, name) for name in _PLAIN}
    for attribute, prefix in _TALLIES.items():
        tally = getattr(result, attribute)
        values |= {f"{prefix}_{name}": getattr(tally, name) for name in _TALLY_FIELDS}
    return values


def _to_result(row: EvaluationRunModel) -> EvaluationResult:
    tallies = {
        attribute: TestTally(**{name: getattr(row, f"{prefix}_{name}") for name in _TALLY_FIELDS})
        for attribute, prefix in _TALLIES.items()
    }
    return EvaluationResult(**{name: getattr(row, name) for name in _PLAIN}, **tallies)


class SqlAlchemyEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, result: EvaluationResult) -> None:
        values = _to_columns(result)
        row = self._session.scalar(
            select(EvaluationRunModel).where(
                EvaluationRunModel.benchmark_id == result.benchmark_id,
                EvaluationRunModel.task_id == result.task_id,
                EvaluationRunModel.system == result.system,
            )
        )
        if row is None:
            self._session.add(EvaluationRunModel(**values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        self._session.commit()

    def recent_benchmarks(self, limit: int) -> list[StoredBenchmark]:
        started = func.min(EvaluationRunModel.created_at).label("started")
        newest = self._session.execute(
            select(EvaluationRunModel.benchmark_id, started)
            .group_by(EvaluationRunModel.benchmark_id)
            .order_by(started.desc(), EvaluationRunModel.benchmark_id)
            .limit(limit)
        ).all()
        if not newest:
            return []
        rows = self._session.scalars(
            select(EvaluationRunModel).where(EvaluationRunModel.benchmark_id.in_([b for b, _ in newest]))
        ).all()
        grouped: dict[str, list[EvaluationResult]] = {b: [] for b, _ in newest}
        for row in rows:
            grouped[row.benchmark_id].append(_to_result(row))
        return [
            # Aggregates bypass the UTC column type on SQLite, so restore the zone here.
            StoredBenchmark(id=b, created_at=s if s.tzinfo else s.replace(tzinfo=UTC), results=grouped[b])
            for b, s in newest
        ]
