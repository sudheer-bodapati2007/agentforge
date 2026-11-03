from typing import List, Optional
from app.models import Item

class ItemRepository:
    def __init__(self):
        self.items = []
        self.next_id = 1

    def create_item(self, item: Item) -> Item:
        new_item = Item(id=self.next_id, name=item.name, price=item.price)
        self.items.append(new_item)
        self.next_id += 1
        return new_item

    def get_item(self, item_id: int) -> Optional[Item]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_all_items(self) -> List[Item]:
        return sorted(self.items, key=lambda x: x.id)