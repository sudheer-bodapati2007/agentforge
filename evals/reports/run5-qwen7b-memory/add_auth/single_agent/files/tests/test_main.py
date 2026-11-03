import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def notes_api_key():
    return 'test_api_key'

@pytest.fixture
def set_env(notes_api_key):
    os.environ['NOTES_API_KEY'] = notes_api_key
    yield
    del os.environ['NOTES_API_KEY']

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_list_notes_without_api_key(set_env):
    response = client.get("/notes")
    assert response.status_code == 401

def test_list_notes_with_wrong_api_key(set_env):
    response = client.get("/notes", headers={"X-API-Key": "wrong_api_key"})
    assert response.status_code == 401

def test_list_notes_with_correct_api_key(set_env):
    response = client.get("/notes", headers={"X-API-Key": os.environ['NOTES_API_KEY']})
    assert response.status_code == 200

def test_add_note_without_api_key(set_env):
    response = client.post("/notes", json={"text": "Test note"})
    assert response.status_code == 401

def test_add_note_with_wrong_api_key(set_env):
    response = client.post("/notes", json={"text": "Test note"}, headers={"X-API-Key": "wrong_api_key"})
    assert response.status_code == 401

def test_add_note_with_correct_api_key(set_env):
    response = client.post("/notes", json={"text": "Test note"}, headers={"X-API-Key": os.environ['NOTES_API_KEY']})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "text": "Test note"}