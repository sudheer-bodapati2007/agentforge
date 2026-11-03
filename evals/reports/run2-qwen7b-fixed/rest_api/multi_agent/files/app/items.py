from typing import List, Optional
from pydantic import BaseModel, validator

class Item(BaseModel):
    id: int
    name: str
    price: float

    class Config:
        orm_mode = True

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

class ItemRepository:
    def __init__(self):
        self.items = []
        self.next_id = 1

    def create_item(self, item: ItemCreate) -> Item:
        new_item = Item(id=self.next_id, name=item.name, price=item.price)
        self.items.append(new_item)
        self.next_id += 1
        return new_item

    def get_item(self, item_id: int) -> Optional[Item]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_items(self) -> List[Item]:
        return sorted(self.items, key=lambda x: x.id)