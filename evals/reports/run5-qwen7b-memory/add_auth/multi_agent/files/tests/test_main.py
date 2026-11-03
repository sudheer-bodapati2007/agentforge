from fastapi.testclient import TestClient
from app.main import app
import os

NOTES_API_KEY = 'test_key'

os.environ['NOTES_API_KEY'] = NOTES_API_KEY

client = TestClient(app)


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_list_notes_with_valid_key():
    response = client.get('/notes', headers={'X-API-Key': NOTES_API_KEY})
    assert response.status_code == 200
    assert response.json() == []


def test_list_notes_with_invalid_key():
    response = client.get('/notes', headers={'X-API-Key': 'wrong_key'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid API key'}


def test_list_notes_without_key():
    response = client.get('/notes')
    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid API key'}


def test_add_note_with_valid_key():
    response = client.post('/notes', headers={'X-API-Key': NOTES_API_KEY}, json={'text': 'Test note'})
    assert response.status_code == 201
    assert response.json() == {'id': 1, 'text': 'Test note'}


def test_add_note_with_invalid_key():
    response = client.post('/notes', headers={'X-API-Key': 'wrong_key'}, json={'text': 'Test note'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid API key'}


def test_add_note_without_key():
    response = client.post('/notes', json={'text': 'Test note'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid API key'}
