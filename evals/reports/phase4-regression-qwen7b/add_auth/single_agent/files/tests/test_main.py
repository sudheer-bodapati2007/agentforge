import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def api_key():
    return 'test_api_key'

@pytest.fixture
def set_api_key(api_key):
    os.environ['NOTES_API_KEY'] = api_key
    yield
    del os.environ['NOTES_API_KEY']

def test_health_endpoint(set_api_key):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}

def test_list_notes_endpoint(set_api_key):
    response = client.get('/notes', headers={'X-API-Key': 'test_api_key'})
    assert response.status_code == 200
    assert response.json() == []

def test_add_note_endpoint(set_api_key):
    response = client.post('/notes', json={'text': 'Test note'}, headers={'X-API-Key': 'test_api_key'})
    assert response.status_code == 201
    assert response.json() == {'id': 1, 'text': 'Test note'}

def test_missing_api_key(set_api_key):
    response = client.get('/notes', headers={'X-API-Key': 'wrong_key'})
    assert response.status_code == 401

def test_empty_api_key(set_api_key):
    os.environ['NOTES_API_KEY'] = ''
    response = client.get('/notes', headers={'X-API-Key': 'test_api_key'})
    assert response.status_code == 401