"""GET /api/evaluations: stored benchmark results, summarised per system."""

from dataclasses import replace
from datetime import UTC, datetime

from app.domain.evaluation import EvaluationResult, SystemKind, TestTally
from app.infrastructure.persistence.evaluation_repository import SqlAlchemyEvaluationRepository
from app.infrastructure.persistence.orm import EvaluationRunModel


def row(benchmark_id="b1", task_id="crud", system=SystemKind.MULTI_AGENT, ref=(10, 10), **changes) -> EvaluationResult:
    values = dict(
        benchmark_id=benchmark_id,
        task_id=task_id,
        task_title=task_id.title(),
        category="CRUD",
        system=system,
        model_name="ollama:qwen2.5-coder:7b",
        demo_model=False,
        own_tests=TestTally(executed=True, passed=4, total=4),
        reference_tests=TestTally(executed=True, passed=ref[0], total=ref[1]),
        debug_iterations=1,
        test_runs=2,
        findings_total=1,
        blocking_findings=0,
        latency_seconds=42.5,
        input_tokens=6000,
        output_tokens=2000,
        estimated_cost_usd=None,
        human_interventions=0,
        error=None,
    )
    return EvaluationResult(**{**values, **changes})


def test_requires_sign_in(anonymous_client):
    assert anonymous_client.get("/api/evaluations").status_code == 401


def test_empty_when_no_benchmark_has_run(client):
    response = client.get("/api/evaluations")
    assert response.status_code == 200
    assert response.json() == {"benchmarks": []}


def test_returns_results_and_summaries(client, db_session):
    repo = SqlAlchemyEvaluationRepository(db_session)
    repo.save(row(system=SystemKind.MULTI_AGENT, ref=(10, 10)))
    repo.save(row(system=SystemKind.SINGLE_AGENT, ref=(6, 10), own_tests=TestTally(executed=False), error="invalid JSON"))

    (benchmark,) = client.get("/api/evaluations").json()["benchmarks"]
    assert benchmark["id"] == "b1"
    assert benchmark["created_at"].endswith(("Z", "+00:00")), "timestamps are UTC on every database"
    assert benchmark["model_names"] == ["ollama:qwen2.5-coder:7b"]
    assert benchmark["demo_model"] is False

    multi, single = benchmark["summaries"]
    assert (multi["system"], multi["solved"], multi["solve_rate"], multi["reference_pass_rate"]) == ("multi_agent", 1, 1.0, 1.0)
    assert (single["solved"], single["solve_rate"], single["reference_pass_rate"]) == (0, 0.0, 0.6)
    assert single["own_suite_success_rate"] is None, "no suite ran: undefined, never 0"
    assert multi["total_cost_usd"] is None, "unpriced model: unknown cost, never 0"
    assert single["errors"] == 1

    by_system = {r["system"]: r for r in benchmark["results"]}
    assert by_system["multi_agent"]["solved"] is True
    assert by_system["single_agent"]["reference_tests"] == {"executed": True, "passed": 6, "total": 10, "errors": 0}
    assert by_system["single_agent"]["error"] == "invalid JSON"


def test_saving_the_same_task_again_replaces_the_row(client, db_session):
    repo = SqlAlchemyEvaluationRepository(db_session)
    repo.save(row(ref=(2, 10)))
    repo.save(row(ref=(10, 10), latency_seconds=12.0))
    assert db_session.query(EvaluationRunModel).count() == 1
    (result,) = client.get("/api/evaluations").json()["benchmarks"][0]["results"]
    assert (result["reference_tests"]["passed"], result["latency_seconds"]) == (10, 12.0)


def test_newest_benchmarks_first_and_limit(client, db_session):
    repo = SqlAlchemyEvaluationRepository(db_session)
    for hour, benchmark_id in enumerate(("b-old", "b-mid", "b-new")):
        repo.save(row(benchmark_id=benchmark_id))
        db_session.query(EvaluationRunModel).filter_by(benchmark_id=benchmark_id).update(
            {"created_at": datetime(2026, 10, 1, hour, tzinfo=UTC)}
        )
    db_session.commit()
    ids =[b["id"] for b in client.get("/api/evaluations").json()["benchmarks"]]
    assert ids == ["b-new", "b-mid", "b-old"]
    assert [b["id"] for b in client.get("/api/evaluations?limit=1").json()["benchmarks"]] == ["b-new"]


def test_limit_is_validated(client):
    for bad in ("0", "21", "abc", "-1"):
        assert client.get(f"/api/evaluations?limit={bad}").status_code == 422


def test_results_are_the_same_for_every_user(client, client_b, db_session):
    SqlAlchemyEvaluationRepository(db_session).save(row())
    assert client.get("/api/evaluations").json() == client_b.get("/api/evaluations").json()


def test_long_errors_and_titles_round_trip(client, db_session):
    long_error = "E" * 500
    SqlAlchemyEvaluationRepository(db_session).save(replace(row(), error=long_error, task_title="T" * 200))
    (result,) = client.get("/api/evaluations").json()["benchmarks"][0]["results"]
    assert result["error"] == long_error and len(result["task_title"]) == 200
