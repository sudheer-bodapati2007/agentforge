from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

items = []
current_id = 0

class Item(BaseModel):
    name: str
    price: float

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: Item):
    global current_id
    current_id += 1
    item.id = current_id
    items.append(item)
    return item

@app.get("/items/{item_id}")
def get_item(item_id: int):
    for item in items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

@app.get("/items")
def get_items():
    return items
