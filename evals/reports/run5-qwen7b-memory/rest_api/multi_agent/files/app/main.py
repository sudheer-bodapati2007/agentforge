from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from app.items import Item, item_repository

app = FastAPI()

# In-memory storage for items
items = []

# Item model with validation
class ItemCreate(BaseModel):
    name: str
    price: float

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty or only whitespace')
        return v

    @validator('price')
    def price_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError('Price cannot be negative')
        return v

# Item repository
item_repository = {
    'next_id': 1
}

# Health check endpoint
@app.get('/health')
def health_check():
    return {'status': 'ok'}

# Create item endpoint
@app.post('/items', status_code=201)
def create_item(item: ItemCreate):
    item_dict = item.dict()
    item_dict['id'] = item_repository['next_id']
    items.append(item_dict)
    item_repository['next_id'] += 1
    return item_dict

# Get item by ID endpoint
@app.get('/items/{item_id}')
def get_item(item_id: int):
    for item in items:
        if item['id'] == item_id:
            return item
    raise HTTPException(status_code=404, detail='Item not found')

# Get all items endpoint
@app.get('/items')
def get_items():
    return sorted(items, key=lambda x: x['id'])