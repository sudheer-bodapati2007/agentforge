from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from typing import List, Optional

app = FastAPI()

items = []
current_id = 0

class Item(BaseModel):
    name: str
    price: float

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace only')
        return v

    @validator('price')
    def price_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError('Price cannot be negative')
        return v

@app.get('/health')
def health_check():
    return {'status': 'ok'}

@app.post('/items', status_code=201)
def create_item(item: Item):
    global current_id
    current_id += 1
    item_dict = item.dict()
    item_dict['id'] = current_id
    items.append(item_dict)
    return item_dict

@app.get('/items/{item_id}', status_code=200)
def get_item(item_id: int):
    for item in items:
        if item['id'] == item_id:
            return item
    raise HTTPException(status_code=404, detail='Item not found')

@app.get('/items', status_code=200)
def get_items():
    return sorted(items, key=lambda x: x['id'])