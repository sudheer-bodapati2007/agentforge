import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.repository import item_repository

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_repository():
    item_repository.items = []
    item_repository.next_id = 1


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_create_item_endpoint():
    item_data = {'name': 'Test Item', 'price': 10.0}
    response = client.post('/items', json=item_data)
    assert response.status_code == 201
    assert response.json()['name'] == item_data['name']
    assert response.json()['price'] == item_data['price']
    assert 'id' in response.json()
    assert response.json()['id'] > 0


def test_get_item_endpoint():
    item_data = {'name': 'Test Item', 'price': 10.0}
    response = client.post('/items', json=item_data)
    item_id = response.json()['id']
    response = client.get(f'/items/{item_id}')
    assert response.status_code == 200
    assert response.json()['id'] == item_id


def test_get_item_not_found_endpoint():
    response = client.get('/items/999')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Item not found'}


def test_get_all_items_endpoint():
    item_data1 = {'name': 'Item 1', 'price': 10.0}
    item_data2 = {'name': 'Item 2', 'price': 20.0}
    client.post('/items', json=item_data1)
    client.post('/items', json=item_data2)
    response = client.get('/items')
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_create_item_missing_name_endpoint():
    item_data = {'name': '', 'price': 10.0}
    response = client.post('/items', json=item_data)
    assert response.status_code == 422


def test_create_item_negative_price_endpoint():
    item_data = {'name': 'Test Item', 'price': -10.0}
    response = client.post('/items', json=item_data)
    assert response.status_code == 422