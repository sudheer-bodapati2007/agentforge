import pytest
from fastapi.testclient import TestClient
from app.main import app, _notes

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_notes():
    _notes.clear()

@pytest.mark.parametrize("api_key, expected_status", [
    (None, 401),
    ("", 401),
    ("wrong_key", 401),
    ("correct_key", 200),
])
def test_health(api_key, expected_status):
    headers = {"X-API-Key": api_key} if api_key else {}
    response = client.get("/health", headers=headers)
    assert response.status_code == expected_status

@pytest.mark.parametrize("api_key, expected_status", [
    (None, 401),
    ("", 401),
    ("wrong_key", 401),
    ("correct_key", 201),
])
def test_add_note(api_key, expected_status):
    headers = {"X-API-Key": api_key} if api_key else {}
    response = client.post("/notes", json={"text": "New note"}, headers=headers)
    assert response.status_code == expected_status

@pytest.mark.parametrize("api_key, expected_status", [
    (None, 401),
    ("", 401),
    ("wrong_key", 401),
    ("correct_key", 200),
])
def test_list_notes(api_key, expected_status):
    headers = {"X-API-Key": api_key} if api_key else {}
    response = client.get("/notes", headers=headers)
    assert response.status_code == expected_status