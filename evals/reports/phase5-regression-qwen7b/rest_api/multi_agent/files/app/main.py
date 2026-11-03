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
def health_check():
    return {'status': 'ok'}

@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: Item):
    global current_id
    current_id += 1
    item_dict = item.model_dump()
    item_dict['id'] = current_id
    items.append(item_dict)
    return item_dict

@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = next((item for item in items if item['id'] == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')
    return item

@app.get("/items")
def get_items():
    return sorted(items, key=lambda x: x['id'])