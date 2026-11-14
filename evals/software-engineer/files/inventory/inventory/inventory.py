"""In-memory inventory. Single process; not thread-safe yet."""


class OutOfStock(Exception):
    pass


class Inventory:
    def __init__(self):
        self._stock = {}

    def add_stock(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._stock[sku] = self._stock.get(sku, 0) + qty

    def remove_stock(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        if self.available(sku) < qty:
            raise OutOfStock(sku)
        self._stock[sku] -= qty

    def available(self, sku: str) -> int:
        return self._stock.get(sku, 0)
