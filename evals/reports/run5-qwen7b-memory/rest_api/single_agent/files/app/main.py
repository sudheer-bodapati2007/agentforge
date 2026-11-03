from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, validator

app = FastAPI()

items = {}
item_id_counter = 0

class Item(BaseModel):
    name: str
    price: float

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('name cannot be empty or only whitespace')
        return v

    @validator('price')
    def price_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError('price cannot be negative')
        return v

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/items', status_code=status.HTTP_201_CREATED)
def create_item(item: Item):
    global item_id_counter
    item_id_counter += 1
    items[item_id_counter] = item
    return {'id': item_id_counter, **item.dict()}

@app.get('/items/{item_id}', status_code=status.HTTP_404_NOT_FOUND)
def read_item(item_id: int):
    item = items.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')
    return item

@app.get('/items')
def read_items():
    return list(items.values())