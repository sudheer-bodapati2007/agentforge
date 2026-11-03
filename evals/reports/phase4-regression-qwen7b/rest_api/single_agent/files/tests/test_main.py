from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_item():
    response = client.post("/items", json={"name": "Laptop", "price": 1200.00})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Laptop", "price": 1200.00}

    response = client.post("/items", json={"name": "Mouse", "price": 25.00})
    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "Mouse", "price": 25.00}

def test_get_item():
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Laptop", "price": 1200.00}

    response = client.get("/items/2")
    assert response.status_code == 200
    assert response.json() == {"id": 2, "name": "Mouse", "price": 25.00}

    response = client.get("/items/3")
    assert response.status_code == 404

def test_get_items():
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Laptop", "price": 1200.00}, {"id": 2, "name": "Mouse", "price": 25.00}]

def test_create_item_validation():
    response = client.post("/items", json={"name": "", "price": 100.00})
    assert response.status_code == 422

    response = client.post("/items", json={"name": "  ", "price": 100.00})
    assert response.status_code == 422

    response = client.post("/items", json={"name": "Keyboard", "price": -10.00})
    assert response.status_code == 422

    response = client.post("/items", json={"name": "Keyboard", "price": 0.00})
    assert response.status_code == 201
