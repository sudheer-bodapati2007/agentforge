class Item:
    def __init__(self, id: int, name: str, price: float):
        self.id = id
        self.name = name
        self.price = price

item_repository = {
    'next_id': 1
}
