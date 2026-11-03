import uuid
from datetime import UTC, datetime

from app.domain.enums import RunStatus
from app.infrastructure.persistence.orm import WorkflowRunModel


def test_create_list_get_project(client, project_payload):
    created = client.post("/api/projects", json=project_payload)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == project_payload["name"]
    assert body["run_count"] == 0
    assert body["latest_run_status"] is None
    assert body["created_at"].endswith(("+00:00", "Z"))

    listing = client.get("/api/projects").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == body["id"]

    fetched = client.get(f"/api/projects/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["requirements"] == project_payload["requirements"]


def test_search_is_case_insensitive_and_escapes_wildcards(client, project_payload):
    client.post("/api/projects", json={**project_payload, "name": "Inventory API"})
    client.post("/api/projects", json={**project_payload, "name": "Chat_bot"})

    assert client.get("/api/projects", params={"q": "inventory"}).json()["total"] == 1
    # "_" must match literally, not as a single-character wildcard.
    assert client.get("/api/projects", params={"q": "t_b"}).json()["total"] == 1
    assert client.get("/api/projects", params={"q": "%"}).json()["total"] == 0


def test_pagination(client, project_payload):
    for i in range(3):
        client.post("/api/projects", json={**project_payload, "name": f"P{i}"})
    page = client.get("/api/projects", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1


def test_update_project(client, project_payload):
    project_id = client.post("/api/projects", json=project_payload).json()["id"]
    response = client.patch(
        f"/api/projects/{project_id}", json={"name": "Renamed", "framework": ""}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["framework"] is None


def test_update_rejects_null_for_required_field(client, project_payload):
    project_id = client.post("/api/projects", json=project_payload).json()["id"]
    response = client.patch(f"/api/projects/{project_id}", json={"name": None})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_delete_project_cascades_runs(client, db_session, project_payload):
    project_id = client.post("/api/projects", json=project_payload).json()["id"]
    db_session.add(WorkflowRunModel(project_id=uuid.UUID(project_id), status=RunStatus.FAILED))
    db_session.commit()

    assert client.get(f"/api/projects/{project_id}").json()["run_count"] == 1
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    db_session.expire_all()
    assert db_session.query(WorkflowRunModel).count() == 0


def test_latest_run_status_reflects_most_recent_run(client, db_session, project_payload):
    project_id = uuid.UUID(client.post("/api/projects", json=project_payload).json()["id"])
    db_session.add_all(
        [
            WorkflowRunModel(
                project_id=project_id,
                status=RunStatus.FAILED,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            WorkflowRunModel(
                project_id=project_id,
                status=RunStatus.COMPLETED,
                created_at=datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ]
    )
    db_session.commit()
    body = client.get(f"/api/projects/{project_id}").json()
    assert body["run_count"] == 2
    assert body["latest_run_status"] == "completed"


def test_not_found_has_structured_error(client):
    response = client.get(f"/api/projects/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_uuid_is_validation_error(client):
    response = client.get("/api/projects/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_validation_errors_do_not_echo_input(client, project_payload):
    response = client.post(
        "/api/projects", json={**project_payload, "requirements": "short-secret-value"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(d["loc"] == ["body", "requirements"] for d in error["details"])
    assert "short-secret-value" not in response.text


def test_unknown_fields_and_languages_are_rejected(client, project_payload):
    assert client.post("/api/projects", json={**project_payload, "owner": "x"}).status_code == 422
    assert (
        client.post("/api/projects", json={**project_payload, "language": "cobol"}).status_code
        == 422
    )
