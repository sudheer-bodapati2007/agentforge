from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, validator
from app.items import ItemRepository, Item

app = FastAPI()

item_repo = ItemRepository()

class ItemCreate(BaseModel):
    name: str
    price: float

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Name cannot be empty or whitespace')
        return v

    @validator('price')
    def price_must_not_be_negative(cls, v):
        if v < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Price cannot be negative')
        return v

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/items', status_code=status.HTTP_201_CREATED, response_model=Item)
def create_item(item: ItemCreate):
    return item_repo.create_item(item)

@app.get('/items/{item_id}', response_model=Item)
def get_item(item_id: int):
    item = item_repo.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Item not found')
    return item

@app.get('/items', response_model=list[Item])
def get_items():
    return item_repo.get_items()
