from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}

def test_create_item():
    response = client.post('/items', json={'name': 'apple', 'price': 0.99})
    assert response.status_code == 201
    assert response.json() == {'id': 1, 'name': 'apple', 'price': 0.99}

    response = client.post('/items', json={'name': 'banana', 'price': 0.50})
    assert response.status_code == 201
    assert response.json() == {'id': 2, 'name': 'banana', 'price': 0.50}

def test_get_item():
    response = client.get('/items/1')
    assert response.status_code == 200
    assert response.json() == {'id': 1, 'name': 'apple', 'price': 0.99}

    response = client.get('/items/2')
    assert response.status_code == 200
    assert response.json() == {'id': 2, 'name': 'banana', 'price': 0.50}

    response = client.get('/items/3')
    assert response.status_code == 404

def test_get_items():
    response = client.get('/items')
    assert response.status_code == 200
    assert response.json() == [{'id': 1, 'name': 'apple', 'price': 0.99}, {'id': 2, 'name': 'banana', 'price': 0.50}]

def test_create_item_with_invalid_name():
    response = client.post('/items', json={'name': '', 'price': 0.99})
    assert response.status_code == 422

    response = client.post('/items', json={'name': '   ', 'price': 0.99})
    assert response.status_code == 422

def test_create_item_with_negative_price():
    response = client.post('/items', json={'name': 'apple', 'price': -0.99})
    assert response.status_code == 422