from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import TOKENS, FakeTokenVerifier, auth_headers, make_settings


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_reports_unconfigured_llm(client):
    status = client.get("/api/system/status").json()
    assert status["database"]["state"] == "ok"
    assert status["llm"]["state"] == "not_configured"
    assert status["llm"]["api_key_present"] is False
    assert status["workflow_engine"]["state"] == "not_configured"
    assert status["sandbox"]["state"] == "ok"  # the fake sandbox reports itself available


def test_status_never_exposes_the_api_key(migrated_database_url):
    secret = "sk-test-should-never-leak"
    app = create_app(
        make_settings(
            migrated_database_url, llm_provider="google", llm_model="gemini-test", llm_api_key=secret
        ),
        token_verifier=FakeTokenVerifier(TOKENS),
    )
    with TestClient(app, headers=auth_headers("token-a")) as client:
        response = client.get("/api/system/status")
    assert response.json()["llm"]["api_key_present"] is True
    assert secret not in response.text


def test_health_degraded_when_database_unreachable():
    # Nothing listens on port 1; the connect timeout keeps this fast.
    settings = make_settings(
        "postgresql+psycopg://u:p@127.0.0.1:1/none", database_connect_timeout_seconds=2
    )
    app = create_app(settings, token_verifier=FakeTokenVerifier(TOKENS))
    with TestClient(app, headers=auth_headers("token-a")) as client:
        health = client.get("/api/health")
        status = client.get("/api/system/status").json()
    assert health.status_code == 503
    assert status["database"] == {"state": "error", "detail": "Database is unreachable"}


def test_data_endpoints_return_503_when_database_unreachable():
    settings = make_settings(
        "postgresql+psycopg://u:p@127.0.0.1:1/none", database_connect_timeout_seconds=2
    )
    app = create_app(settings, token_verifier=FakeTokenVerifier(TOKENS))
    with TestClient(app, headers=auth_headers("token-a"), raise_server_exceptions=False) as client:
        for path in ("/api/dashboard/metrics", "/api/projects"):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "database_unavailable"
            assert "127.0.0.1" not in response.text


def test_oversized_request_body_is_rejected(migrated_database_url):
    app = create_app(
        make_settings(migrated_database_url, max_request_bytes=100),
        token_verifier=FakeTokenVerifier(TOKENS),
    )
    with TestClient(app, headers=auth_headers("token-a")) as client:
        response = client.post("/api/projects", content=b"x" * 500, headers={"content-type": "application/json"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_chunked_oversized_body_is_rejected(migrated_database_url):
    app = create_app(
        make_settings(migrated_database_url, max_request_bytes=100),
        token_verifier=FakeTokenVerifier(TOKENS),
    )

    def chunks():
        for _ in range(10):
            yield b"x" * 50

    with TestClient(app, headers=auth_headers("token-a")) as client:
        response = client.post(
            "/api/projects", content=chunks(), headers={"content-type": "application/json"}
        )
    assert response.status_code == 413
