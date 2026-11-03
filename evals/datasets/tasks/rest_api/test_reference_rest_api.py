"""Hidden reference tests for the rest_api task. Tests share one app instance, so they
never assume an empty store: each one checks only the items it created."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create(name="Widget", price=2.5):
    return client.post("/items", json={"name": name, "price": price})


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_returns_201_with_item():
    response = create("Lamp", 19.99)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Lamp"
    assert body["price"] == 19.99
    assert isinstance(body["id"], int) and body["id"] > 0


def test_ids_increase_by_one():
    first = create("A", 1).json()["id"]
    second = create("B", 2).json()["id"]
    assert second == first + 1


def test_get_item_by_id():
    created = create("Chair", 45).json()
    response = client.get(f"/items/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_unknown_item_is_404():
    assert client.get("/items/999999").status_code == 404


def test_list_contains_created_items_in_id_order():
    ids = [create(f"Item {n}", n).json()["id"] for n in range(3)]
    items = client.get("/items").json()
    listed = [item["id"] for item in items]
    assert all(i in listed for i in ids)
    assert listed == sorted(listed)


def test_zero_price_is_allowed():
    assert create("Free sample", 0).status_code == 201


def test_missing_name_is_422():
    assert client.post("/items", json={"price": 1}).status_code == 422


def test_empty_name_is_422():
    assert create("", 1).status_code == 422


def test_whitespace_name_is_422():
    assert create("   ", 1).status_code == 422


def test_negative_price_is_422():
    assert create("Broken", -0.01).status_code == 422
