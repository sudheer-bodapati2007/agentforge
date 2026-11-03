import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

items = []
current_id = 0

@pytest.fixture(autouse=True)
def cleanup_items():
    global items, current_id
    items = []
    current_id = 0

@pytest.fixture(autouse=True)
def reset_current_id():
    global current_id
    current_id = 0

def test_health_check():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}

def test_create_item_success():
    response = client.post('/items', json={'name': 'test item', 'price': 10.0})
    assert response.status_code == 201
    assert response.json()['id'] == 1
    assert response.json()['name'] == 'test item'
    assert response.json()['price'] == 10.0
    items.append(response.json())

def test_get_item_success():
    response = client.post('/items', json={'name': 'test item', 'price': 10.0})
    item_id = response.json()['id']
    response = client.get(f'/items/{item_id}')
    assert response.status_code == 200
    assert response.json()['id'] == item_id
    assert response.json()['name'] == 'test item'
    assert response.json()['price'] == 10.0
    items.append(response.json())

def test_get_item_not_found():
    response = client.post('/items', json={'name': 'test item', 'price': 10.0})
    item_id = response.json()['id']
    response = client.get(f'/items/{item_id}')
    assert response.status_code == 200
    assert response.json()['id'] == item_id
    assert response.json()['name'] == 'test item'
    assert response.json()['price'] == 10.0
    items.append(response.json())
    response = client.get('/items/1')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Item not found'}

def test_get_items_success():
    response = client.post('/items', json={'name': 'item1', 'price': 5.0})
    items.append(response.json())
    response = client.post('/items', json={'name': 'item2', 'price': 15.0})
    items.append(response.json())
    response = client.get('/items')
    assert response.status_code == 200
    assert response.json() == [{'id': 1, 'name': 'item1', 'price': 5.0}, {'id': 2, 'name': 'item2', 'price': 15.0}]

def test_create_item_invalid_name():
    response = client.post('/items', json={'name': '', 'price': 10.0})
    assert response.status_code == 422

def test_create_item_invalid_price():
    response = client.post('/items', json={'name': 'test item', 'price': -10.0})
    assert response.status_code == 422