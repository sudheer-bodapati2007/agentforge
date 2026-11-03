from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}

def test_create_item():
    response = client.post('/items', json={'name': 'item1', 'price': 10.0})
    assert response.status_code == 201
    assert response.json() == {'id': 1, 'name': 'item1', 'price': 10.0}

    response = client.post('/items', json={'name': 'item2', 'price': 20.0})
    assert response.status_code == 201
    assert response.json() == {'id': 2, 'name': 'item2', 'price': 20.0}

def test_read_item():
    response = client.post('/items', json={'name': 'item1', 'price': 10.0})
    assert response.status_code == 201
    item_id = response.json()['id']

    response = client.get(f'/items/{item_id}')
    assert response.status_code == 200
    assert response.json() == {'id': item_id, 'name': 'item1', 'price': 10.0}

    response = client.get('/items/999')
    assert response.status_code == 404

def test_read_items():
    response = client.post('/items', json={'name': 'item1', 'price': 10.0})
    assert response.status_code == 201
    response = client.post('/items', json={'name': 'item2', 'price': 20.0})
    assert response.status_code == 201

    response = client.get('/items')
    assert response.status_code == 200
    assert response.json() == [{'id': 1, 'name': 'item1', 'price': 10.0}, {'id': 2, 'name': 'item2', 'price': 20.0}]

def test_create_item_validation():
    response = client.post('/items', json={'name': '', 'price': 10.0})
    assert response.status_code == 422

    response = client.post('/items', json={'name': 'item1', 'price': -10.0})
    assert response.status_code == 422

    response = client.post('/items', json={'name': 'item1', 'price': 0.0})
    assert response.status_code == 201