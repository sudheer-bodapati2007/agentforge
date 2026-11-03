"""The backend, not the UI, enforces authentication and per-user data isolation."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import RunStatus
from app.infrastructure.persistence.orm import ProjectModel, WorkflowRunModel
from app.main import create_app
from tests.conftest import USER_A, auth_headers, make_settings

PROTECTED = [
    ("GET", "/api/projects"),
    ("POST", "/api/projects"),
    ("GET", f"/api/projects/{uuid.uuid4()}"),
    ("PATCH", f"/api/projects/{uuid.uuid4()}"),
    ("DELETE", f"/api/projects/{uuid.uuid4()}"),
    ("GET", "/api/dashboard/metrics"),
    ("GET", "/api/system/status"),
    ("GET", "/api/me"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_routes_require_a_token(anonymous_client, method, path):
    response = anonymous_client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_rejected(anonymous_client):
    response = anonymous_client.get("/api/projects", headers=auth_headers("forged"))
    assert response.status_code == 401


def test_health_stays_public(anonymous_client):
    assert anonymous_client.get("/api/health").status_code == 200


def test_me_returns_the_verified_user(client):
    body = client.get("/api/me").json()
    assert body["id"] == str(USER_A.id)
    assert body["email"] == USER_A.email


def test_users_cannot_see_or_change_each_others_projects(client, client_b, project_payload):
    project_id = client.post("/api/projects", json=project_payload).json()["id"]

    assert client_b.get("/api/projects").json()["total"] == 0
    # Another user's project is "not found", never "forbidden" (no existence leak).
    assert client_b.get(f"/api/projects/{project_id}").status_code == 404
    assert client_b.patch(f"/api/projects/{project_id}", json={"name": "pwned"}).status_code == 404
    assert client_b.delete(f"/api/projects/{project_id}").status_code == 404

    owner_view = client.get(f"/api/projects/{project_id}").json()
    assert owner_view["name"] == project_payload["name"]


def test_owner_cannot_be_set_by_the_client(client, client_b, project_payload):
    response = client.post("/api/projects", json={**project_payload, "owner_id": str(uuid.uuid4())})
    assert response.status_code == 422  # unknown field, rejected by the schema


def test_dashboard_counts_only_the_callers_data(client, client_b, db_session, project_payload):
    project_id = uuid.UUID(client.post("/api/projects", json=project_payload).json()["id"])
    db_session.add(WorkflowRunModel(project_id=project_id, status=RunStatus.COMPLETED))
    db_session.commit()

    assert client.get("/api/dashboard/metrics").json()["total_runs"] == 1
    other = client_b.get("/api/dashboard/metrics").json()
    assert other["total_projects"] == 0
    assert other["total_runs"] == 0
    assert other["recent_runs"] == []


def test_legacy_projects_without_owner_are_invisible(client, db_session):
    db_session.add(ProjectModel(name="Pre-auth", requirements="r" * 30, owner_id=None))
    db_session.commit()
    assert client.get("/api/projects").json()["total"] == 0


def test_auth_fails_closed_when_not_configured(migrated_database_url):
    app = create_app(make_settings(migrated_database_url, supabase_url=None))
    with TestClient(app, headers=auth_headers("anything")) as client:
        response = client.get("/api/projects")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_unavailable"
