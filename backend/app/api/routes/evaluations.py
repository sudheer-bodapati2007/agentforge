from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, EvaluationServiceDep
from app.api.schemas.evaluation import Benchmark, BenchmarkList
from app.application.evaluation.service import MAX_BENCHMARKS

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("", response_model=BenchmarkList)
def list_benchmarks(
    _: CurrentUser,
    service: EvaluationServiceDep,
    limit: Annotated[int, Query(ge=1, le=MAX_BENCHMARKS)] = 5,
) -> BenchmarkList:
    """Recent benchmark results (platform-level data, the same for every signed-in user)."""
    return BenchmarkList(benchmarks=[Benchmark.model_validate(b) for b in service.recent(limit)])
