import uuid
from datetime import UTC, datetime, timedelta

from app.domain.enums import RunStatus
from app.infrastructure.persistence.orm import TestResultModel, WorkflowRunModel


def test_empty_database_reports_no_data(client):
    metrics = client.get("/api/dashboard/metrics").json()
    assert metrics["total_projects"] == 0
    assert metrics["total_runs"] == 0
    assert metrics["completion_rate"] is None
    assert metrics["test_pass_rate"] is None
    assert metrics["average_duration_seconds"] is None
    assert metrics["total_estimated_cost_usd"] is None
    assert metrics["recent_runs"] == []


def test_metrics_are_computed_from_persisted_records(client, db_session, project_payload):
    project_id = uuid.UUID(client.post("/api/projects", json=project_payload).json()["id"])
    start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    completed = WorkflowRunModel(
        project_id=project_id,
        status=RunStatus.COMPLETED,
        started_at=start,
        finished_at=start + timedelta(seconds=30),
        estimated_cost_usd=0.25,
    )
    failed = WorkflowRunModel(
        project_id=project_id,
        status=RunStatus.FAILED,
        started_at=start,
        finished_at=start + timedelta(seconds=90),
        estimated_cost_usd=0.5,
    )
    running = WorkflowRunModel(project_id=project_id, status=RunStatus.RUNNING, started_at=start)
    db_session.add_all([completed, failed, running])
    db_session.flush()
    db_session.add_all(
        [
            TestResultModel(run_id=completed.id, command="pytest", executed=True, total=4, passed=4),
            TestResultModel(run_id=failed.id, command="pytest", executed=True, total=4, passed=1, failed=3),
            # Generated but never executed: must not affect the pass rate.
            TestResultModel(run_id=running.id, command="pytest", executed=False, total=10),
        ]
    )
    db_session.commit()

    metrics = client.get("/api/dashboard/metrics").json()
    assert metrics["total_projects"] == 1
    assert metrics["total_runs"] == 3
    assert metrics["runs_by_status"]["running"] == 1
    assert metrics["completion_rate"] == 0.5
    assert metrics["test_pass_rate"] == 5 / 8
    assert metrics["executed_test_suites"] == 2
    assert metrics["average_duration_seconds"] == 60.0
    assert metrics["total_estimated_cost_usd"] == 0.75
    assert len(metrics["recent_runs"]) == 3
    assert metrics["recent_runs"][0]["project_name"] == project_payload["name"]
