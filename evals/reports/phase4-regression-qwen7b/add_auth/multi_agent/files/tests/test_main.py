from fastapi.testclient import TestClient
from app.main import app
from app.auth import validate_api_key
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
    assert response.json() == _notes


def test_list_notes_with_invalid_key():
    response = client.get('/notes', headers={'X-API-Key': 'wrong_key'})
    assert response.status_code == 401


def test_list_notes_without_key():
    response = client.get('/notes')
    assert response.status_code == 401


def test_add_note_with_valid_key():
    note = {'text': 'New Note'}
    response = client.post('/notes', json=note, headers={'X-API-Key': NOTES_API_KEY})
    assert response.status_code == 201
    assert response.json()['text'] == note['text']


def test_add_note_with_invalid_key():
    note = {'text': 'New Note'}
    response = client.post('/notes', json=note, headers={'X-API-Key': 'wrong_key'})
    assert response.status_code == 401


def test_add_note_without_key():
    note = {'text': 'New Note'}
    response = client.post('/notes', json=note)
    assert response.status_code == 401
