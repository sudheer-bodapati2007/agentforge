Build a small REST API with FastAPI. In `app/main.py`, create the FastAPI application object and name it `app`.

Endpoints:
- `GET /health` returns `{"status": "ok"}`.
- `POST /items` takes a JSON body `{"name": str, "price": float}` and responds with status 201 and `{"id": int, "name": str, "price": float}`. Each new item gets a positive integer id, one higher than the previous item's id.
- `GET /items/{item_id}` returns that item, or status 404 if no item has that id.
- `GET /items` returns the list of all items, ordered by id.

Validation: respond with status 422 when `name` is missing, when `name` is empty or only whitespace, or when `price` is negative. A price of 0 is allowed.

Store items in memory. No database.
