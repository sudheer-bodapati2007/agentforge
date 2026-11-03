from fastapi.testclient import TestClient
from app.main import app
import os

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_list_notes_endpoint_with_valid_api_key():
    os.environ["NOTES_API_KEY"] = "test_key"
    response = client.get("/notes", headers={"X-API-Key": "test_key"})
    assert response.status_code == 200
    assert response.json() == []

def test_list_notes_endpoint_with_invalid_api_key():
    os.environ["NOTES_API_KEY"] = "test_key"
    response = client.get("/notes", headers={"X-API-Key": "wrong_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}

def test_list_notes_endpoint_with_missing_api_key():
    os.environ["NOTES_API_KEY"] = ""
    response = client.get("/notes")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}

def test_add_note_endpoint_with_valid_api_key():
    os.environ["NOTES_API_KEY"] = "test_key"
    response = client.post("/notes", json={"text": "Test note"}, headers={"X-API-Key": "test_key"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "text": "Test note"}

def test_add_note_endpoint_with_invalid_api_key():
    os.environ["NOTES_API_KEY"] = "test_key"
    response = client.post("/notes", json={"text": "Test note"}, headers={"X-API-Key": "wrong_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}

def test_add_note_endpoint_with_missing_api_key():
    os.environ["NOTES_API_KEY"] = ""
    response = client.post("/notes", json={"text": "Test note"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}