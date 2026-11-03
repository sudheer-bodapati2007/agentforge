"""Read side of the benchmark: stored results plus the summaries derived from them.

Benchmark results describe the platform, not a user's data: they are written only by
the benchmark command and are readable by any signed-in user.
"""

from dataclasses import dataclass
from datetime import datetime

from app.application.evaluation.ports import EvaluationRepository
from app.domain.evaluation import EvaluationResult, SystemSummary, summarize

MAX_BENCHMARKS = 20


@dataclass(frozen=True)
class BenchmarkReport:
    id: str
    created_at: datetime
    model_names: list[str]
    demo_model: bool
    summaries: list[SystemSummary]
    results: list[EvaluationResult]


class EvaluationService:
    def __init__(self, repository: EvaluationRepository) -> None:
        self._repository = repository

    def recent(self, limit: int = 5) -> list[BenchmarkReport]:
        limit = max(1, min(limit, MAX_BENCHMARKS))
        return [
            BenchmarkReport(
                id=stored.id,
                created_at=stored.created_at,
                model_names=sorted({r.model_name for r in stored.results}),
                demo_model=any(r.demo_model for r in stored.results),
                summaries=summarize(stored.results),
                results=sorted(stored.results, key=lambda r: (r.task_id, r.system.value)),
            )
            for stored in self._repository.recent_benchmarks(limit)
        ]
