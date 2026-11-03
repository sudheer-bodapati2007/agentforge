"""Workflow runs through the HTTP API, the database-backed queue and the checkpointer."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.application.llm import LLMError
from app.main import create_app
from tests.conftest import TOKENS, FakeTokenVerifier, auth_headers, drain, make_settings
from tests.fakes import FakeSandbox, ScenarioLLM, failing_report, passing_report


@pytest.fixture
def fake_llm():
    return ScenarioLLM()


@pytest.fixture
def project_id(client, project_payload):
    return client.post("/api/projects", json=project_payload).json()["id"]


def start(client, project_id, **body):
    return client.post(f"/api/projects/{project_id}/runs", json=body or {"require_approval": False})


def test_run_executes_to_completion(app, client, project_id):
    response = start(client, project_id)
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "queued"
    assert run["llm_model"] == "scripted-demo" and run["demo_model"] is False  # ScenarioLLM is not a demo

    assert drain(app) == 1
    done = client.get(f"/api/runs/{run['id']}").json()
    assert done["status"] == "completed"
    assert done["input_tokens"] > 0 and done["final_report"]["outcome"] == "completed"
    assert done["duration_seconds"] is not None

    agents = client.get(f"/api/runs/{run['id']}/agents").json()
    # The project's database preference is PostgreSQL, so the schema step runs too.
    assert [a["node"] for a in agents][:5] == ["plan", "architect", "schema", "code", "write_tests"]
    assert all(a["status"] == "completed" for a in agents)

    artifacts = {a["path"]: a for a in client.get(f"/api/runs/{run['id']}/artifacts").json()}
    assert {"app/main.py", "tests/test_api.py", "README.md"} <= set(artifacts)
    assert artifacts["tests/test_api.py"]["kind"] == "test"

    content = client.get(f"/api/runs/{run['id']}/artifacts/content", params={"path": "app/main.py"}).json()
    assert "FastAPI" in content["content"]

    tests = client.get(f"/api/runs/{run['id']}/tests").json()
    assert tests[0]["executed"] is True and tests[0]["passed"] == tests[0]["total"]

    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/runs/{run['id']}/download").content))
    assert "app/main.py" in archive.namelist()

    events = client.get(f"/api/runs/{run['id']}/events").json()
    types = [e["type"] for e in events]
    assert types[0] == "run.queued" and types[-1] == "run.finished"
    assert [e["id"] for e in events] == sorted(e["id"] for e in events)

    listed = client.get("/api/runs", params={"project_id": project_id}).json()
    assert listed["total"] == 1


def test_project_shows_latest_run_and_dashboard_counts_it(app, client, project_id):
    start(client, project_id)
    drain(app)
    assert client.get(f"/api/projects/{project_id}").json()["latest_run_status"] == "completed"
    metrics = client.get("/api/dashboard/metrics").json()
    assert metrics["total_runs"] == 1 and metrics["completion_rate"] == 1.0
    assert metrics["test_pass_rate"] == 1.0


def test_debug_loop_and_retry_limit_visible_through_api(app, client, project_id, fake_sandbox):
    fake_sandbox.reports = [failing_report()]
    run_id = start(client, project_id).json()["id"]
    drain(app)
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "partially_completed"
    assert run["debug_iterations"] == run["max_debug_iterations"] == 3
    attempts = client.get(f"/api/runs/{run_id}/tests").json()
    assert [t["attempt"] for t in attempts] == [1, 2, 3, 4]
    assert all(t["failed"] == 1 for t in attempts)


def test_human_approval_flow(app, client, client_b, project_id):
    run_id = start(client, project_id, require_approval=True).json()["id"]
    drain(app)
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "awaiting_approval"
    approvals = client.get(f"/api/runs/{run_id}/approvals").json()
    assert len(approvals) == 1 and approvals[0]["status"] == "pending" and approvals[0]["kind"] == "plan"
    approval_id = approvals[0]["id"]

    # Another user can neither see nor decide it.
    assert client_b.post(f"/api/runs/{run_id}/approvals/{approval_id}", json={"approve": True}).status_code == 404

    decided = client.post(f"/api/runs/{run_id}/approvals/{approval_id}", json={"approve": True, "comment": "ok"})
    assert decided.status_code == 200 and decided.json()["status"] == "approved"
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "queued"
    again = client.post(f"/api/runs/{run_id}/approvals/{approval_id}", json={"approve": False})
    assert again.status_code == 409

    drain(app)
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"


def test_rejecting_the_plan_cancels(app, client, project_id):
    run_id = start(client, project_id, require_approval=True).json()["id"]
    drain(app)
    approval_id = client.get(f"/api/runs/{run_id}/approvals").json()[0]["id"]
    client.post(f"/api/runs/{run_id}/approvals/{approval_id}", json={"approve": False})
    drain(app)
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "cancelled"
    assert client.get(f"/api/runs/{run_id}/artifacts").json() == []


def test_failed_run_can_be_resumed_from_checkpoint(app, client, project_id, fake_llm):
    fake_llm.overrides["coder"] = [LLMError("The coder model was overloaded"), None]
    run_id = start(client, project_id).json()["id"]
    drain(app)
    failed = client.get(f"/api/runs/{run_id}").json()
    assert failed["status"] == "failed" and "overloaded" in failed["error"]

    assert client.post(f"/api/runs/{run_id}/resume").json()["status"] == "queued"
    drain(app)
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"
    assert fake_llm.calls.count("planner") == 1  # completed steps were not repeated


def test_idempotency_key_returns_the_original_run(client, project_id):
    headers = {"Idempotency-Key": "click-123456"}
    first = client.post(f"/api/projects/{project_id}/runs", json={"require_approval": False}, headers=headers)
    second = client.post(f"/api/projects/{project_id}/runs", json={"require_approval": False}, headers=headers)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_active_run_quota(client, project_id):
    assert start(client, project_id).status_code == 201
    assert start(client, project_id).status_code == 201
    third = start(client, project_id)
    assert third.status_code == 429 and third.json()["error"]["code"] == "rate_limited"


def test_cancel_queued_run(client, project_id):
    run_id = start(client, project_id).json()["id"]
    assert client.post(f"/api/runs/{run_id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 409


def test_runs_are_private(client, client_b, project_id):
    run_id = start(client, project_id).json()["id"]
    assert client_b.get(f"/api/runs/{run_id}").status_code == 404
    assert client_b.get(f"/api/runs/{run_id}/artifacts").status_code == 404
    assert client_b.get(f"/api/runs/{run_id}/stream").status_code == 404
    assert client_b.get("/api/runs").json()["total"] == 0
    assert client_b.post(f"/api/projects/{project_id}/runs", json={}).status_code == 404


def test_only_python_projects_can_run(client, project_payload):
    project_id = client.post("/api/projects", json={**project_payload, "language": "typescript"}).json()["id"]
    response = start(client, project_id)
    assert response.status_code == 422


def test_artifact_path_traversal_is_rejected(app, client, project_id):
    run_id = start(client, project_id).json()["id"]
    drain(app)
    response = client.get(f"/api/runs/{run_id}/artifacts/content", params={"path": "../../etc/passwd"})
    assert response.status_code == 422


def test_sse_stream_replays_events_and_ends(app, client, project_id):
    run_id = start(client, project_id).json()["id"]
    drain(app)
    with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    blocks = [b for b in body.split("\n\n") if b.strip()]
    assert blocks[0].startswith("id: ") and "event: run.queued" in blocks[0]
    assert blocks[-1].startswith("event: end")
    last_id = int([b for b in blocks if b.startswith("id: ")][-1].split("\n")[0][4:])
    with client.stream("GET", f"/api/runs/{run_id}/stream", headers={"Last-Event-ID": str(last_id)}) as response:
        replay = "".join(response.iter_text())
    assert replay.strip().startswith("event: end")  # nothing missed, nothing duplicated
    data = json.loads(blocks[0].split("data: ", 1)[1])
    assert data["type"] == "run.queued"


def test_starting_a_run_without_llm_is_503(migrated_database_url, project_payload):
    app = create_app(make_settings(migrated_database_url), token_verifier=FakeTokenVerifier(TOKENS), sandbox=FakeSandbox(), run_workers=False)
    with TestClient(app, headers=auth_headers("token-a")) as client:
        project_id = client.post("/api/projects", json=project_payload).json()["id"]
        response = start(client, project_id)
        client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 503 and response.json()["error"]["code"] == "capability_unavailable"


def test_status_reports_ready_engine_and_sandbox(client):
    status = client.get("/api/system/status").json()
    assert status["llm"]["state"] == "ok"
    assert status["sandbox"]["state"] == "ok"
