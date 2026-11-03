from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, validator
from typing import List, Optional, Dict

app = FastAPI()

items: Dict[int, Dict[str, Optional[str] | float]] = {}
item_id_counter = 0

class Item(BaseModel):
    name: str
    price: float

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('name must not be empty or only whitespace')
        return v

    @validator('price')
    def price_must_not_be_negative(cls, v):
        if v < 0:
            raise ValueError('price must not be negative')
        return v

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/items', status_code=status.HTTP_201_CREATED)
def create_item(item: Item):
    global item_id_counter
    item_id_counter += 1
    items[item_id_counter] = {'name': item.name, 'price': item.price}
    return {'id': item_id_counter, **item.dict()}

@app.get('/items/{item_id}', status_code=status.HTTP_404_NOT_FOUND)
def get_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')
    return items[item_id]

@app.get('/items')
def get_items():
    return list(items.values())