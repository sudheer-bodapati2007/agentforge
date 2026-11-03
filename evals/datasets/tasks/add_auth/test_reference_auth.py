"""Hidden reference tests for the add_auth task."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
KEY = "reference-" + "key-value"


@pytest.fixture(autouse=True)
def configured_key(monkeypatch):
    monkeypatch.setenv("NOTES_API_KEY", KEY)


def test_health_is_public():
    assert client.get("/health").status_code == 200


def test_missing_key_is_401():
    assert client.get("/notes").status_code == 401


def test_wrong_key_is_401():
    assert client.get("/notes", headers={"X-API-Key": "wrong"}).status_code == 401


def test_correct_key_lists_notes():
    response = client.get("/notes", headers={"X-API-Key": KEY})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_correct_key_creates_note():
    response = client.post("/notes", json={"text": "hello"}, headers={"X-API-Key": KEY})
    assert response.status_code == 201
    assert response.json()["text"] == "hello"


def test_post_without_key_is_401_and_creates_nothing():
    before = len(client.get("/notes", headers={"X-API-Key": KEY}).json())
    assert client.post("/notes", json={"text": "sneaky"}).status_code == 401
    assert len(client.get("/notes", headers={"X-API-Key": KEY}).json()) == before


def test_key_is_read_per_request(monkeypatch):
    monkeypatch.setenv("NOTES_API_KEY", "rotated-" + "value")
    assert client.get("/notes", headers={"X-API-Key": KEY}).status_code == 401
    assert client.get("/notes", headers={"X-API-Key": "rotated-value"}).status_code == 200


def test_unset_key_denies_everything(monkeypatch):
    monkeypatch.delenv("NOTES_API_KEY")
    assert client.get("/notes").status_code == 401
    assert client.get("/notes", headers={"X-API-Key": ""}).status_code == 401


def test_empty_key_denies_everything(monkeypatch):
    monkeypatch.setenv("NOTES_API_KEY", "")
    assert client.get("/notes", headers={"X-API-Key": ""}).status_code == 401
