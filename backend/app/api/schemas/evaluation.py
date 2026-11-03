from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.evaluation import SystemKind


class TestTally(BaseModel):
    __test__ = False
    model_config = ConfigDict(from_attributes=True)

    executed: bool
    passed: int
    total: int
    errors: int


class EvaluationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    task_title: str
    category: str
    system: SystemKind
    model_name: str
    solved: bool
    own_tests: TestTally
    reference_tests: TestTally
    debug_iterations: int
    test_runs: int
    findings_total: int
    blocking_findings: int
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    human_interventions: int
    error: str | None


class SystemSummary(BaseModel):
    """Rates are null when undefined; clients must not render null as 0."""

    model_config = ConfigDict(from_attributes=True)

    system: SystemKind
    tasks: int
    solved: int
    solve_rate: float | None
    reference_pass_rate: float | None
    own_suite_success_rate: float | None
    mean_debug_iterations: float | None
    median_latency_seconds: float | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float | None
    blocking_findings: int
    errors: int


class Benchmark(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    model_names: list[str]
    demo_model: bool
    summaries: list[SystemSummary]
    results: list[EvaluationResult]


class BenchmarkList(BaseModel):
    benchmarks: list[Benchmark]
