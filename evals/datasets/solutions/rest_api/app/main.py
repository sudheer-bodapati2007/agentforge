from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI()
_items: dict[int, dict] = {}
_next_id = 1


class ItemIn(BaseModel):
    name: str
    price: float = Field(ge=0)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/items", status_code=201)
def create_item(item: ItemIn):
    global _next_id
    stored = {"id": _next_id, "name": item.name, "price": item.price}
    _items[_next_id] = stored
    _next_id += 1
    return stored


@app.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="item not found")
    return _items[item_id]


@app.get("/items")
def list_items():
    return [_items[key] for key in sorted(_items)]
