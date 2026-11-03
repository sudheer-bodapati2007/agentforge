import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}

def test_create_item_success():
    response = client.post('/items', json={'name': 'Test Item', 'price': 10.0})
    assert response.status_code == 201
    assert response.json()['name'] == 'Test Item'
    assert response.json()['price'] == 10.0
    assert response.json()['id'] == 1

def test_create_item_invalid_name():
    response = client.post('/items', json={'name': '', 'price': 10.0})
    assert response.status_code == 422

    response = client.post('/items', json={'name': '   ', 'price': 10.0})
    assert response.status_code == 422

def test_create_item_negative_price():
    response = client.post('/items', json={'name': 'Test Item', 'price': -1.0})
    assert response.status_code == 422

def test_read_item_success():
    response = client.post('/items', json={'name': 'Test Item', 'price': 10.0})
    item_id = response.json()['id']
    response = client.get(f'/items/{item_id}')
    assert response.status_code == 200
    assert response.json()['id'] == item_id

def test_read_item_not_found():
    response = client.get('/items/999')
    assert response.status_code == 404

def test_read_items_success():
    response = client.post('/items', json={'name': 'Item 1', 'price': 10.0})
    response = client.post('/items', json={'name': 'Item 2', 'price': 20.0})
    response = client.get('/items')
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]['id'] == 1
    assert response.json()[1]['id'] == 2