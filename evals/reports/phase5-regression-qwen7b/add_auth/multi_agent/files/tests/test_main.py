from fastapi.testclient import TestClient
from app.main import app
from app.config import get_api_key
import os



def test_health_endpoint_is_public():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}



def test_notes_endpoint_requires_api_key():
    os.environ["NOTES_API_KEY"] = "valid_key"
    client = TestClient(app)
    response = client.get("/notes")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}



def test_notes_endpoint_with_invalid_api_key():
    os.environ["NOTES_API_KEY"] = "valid_key"
    client = TestClient(app)
    response = client.get("/notes", headers={"X-API-Key": "wrong_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}



def test_notes_endpoint_with_valid_api_key():
    os.environ["NOTES_API_KEY"] = "valid_key"
    client = TestClient(app)
    response = client.get("/notes", headers={"X-API-Key": "valid_key"})
    assert response.status_code == 200
    assert response.json() == []



def test_add_note_endpoint_requires_api_key():
    os.environ["NOTES_API_KEY"] = "valid_key"
    client = TestClient(app)
    response = client.post("/notes", json={"text": "New note"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}



def test_add_note_endpoint_with_invalid_api_key():
    os.environ["NOTES_API_KEY"] = "valid_key"
    client = TestClient(app)
    response = client.post("/notes", json={"text": "New note"}, headers={"X-API-Key": "wrong_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}



def test_add_note_endpoint_with_valid_api_key():
    os.environ["NOTES_API_KEY"] = "valid_key"
    client = TestClient(app)
    response = client.post("/notes", json={"text": "New note"}, headers={"X-API-Key": "valid_key"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "text": "New note"}



def test_add_note_endpoint_with_empty_api_key():
    os.environ["NOTES_API_KEY"] = ""
    client = TestClient(app)
    response = client.post("/notes", json={"text": "New note"}, headers={"X-API-Key": ""})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}



def test_add_note_endpoint_with_unset_api_key():
    os.environ.pop("NOTES_API_KEY", None)
    client = TestClient(app)
    response = client.post("/notes", json={"text": "New note"}, headers={"X-API-Key": "any_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}