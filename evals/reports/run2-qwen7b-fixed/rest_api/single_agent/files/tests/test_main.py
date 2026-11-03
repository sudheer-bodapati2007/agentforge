import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_item():
    response = client.post("/items", json={"name": "item1", "price": 10.0})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "item1", "price": 10.0}

    response = client.post("/items", json={"name": "item2", "price": 20.0})
    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "item2", "price": 20.0}

def test_get_item():
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "item1", "price": 10.0}

    response = client.get("/items/2")
    assert response.status_code == 200
    assert response.json() == {"id": 2, "name": "item2", "price": 20.0}

    response = client.get("/items/3")
    assert response.status_code == 404

def test_get_items():
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "item1", "price": 10.0}, {"id": 2, "name": "item2", "price": 20.0}]

def test_create_item_validation():
    response = client.post("/items", json={"name": "", "price": 10.0})
    assert response.status_code == 422

    response = client.post("/items", json={"name": " ", "price": 10.0})
    assert response.status_code == 422

    response = client.post("/items", json={"name": "item1", "price": -10.0})
    assert response.status_code == 422

    response = client.post("/items", json={"name": "item1", "price": 0.0})
    assert response.status_code == 201
