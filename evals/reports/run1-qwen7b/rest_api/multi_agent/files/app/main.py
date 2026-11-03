from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from app.repository import ItemRepository

app = FastAPI()

item_repository = ItemRepository()

class Item(BaseModel):
    name: str
    price: float

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty or only whitespace')
        return v

    @validator('price')
    def price_must_not_be_negative(cls, v):
        if v < 0:
            raise ValueError('Price cannot be negative')
        return v

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/items', status_code=201)
def create_item(item: Item):
    new_item = item_repository.create_item(item)
    return new_item

@app.get('/items/{item_id}')
def get_item(item_id: int):
    item = item_repository.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Item not found')
    return item

@app.get('/items')
def get_items():
    return item_repository.get_all_items()