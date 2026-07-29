import datetime

from pip._internal.network import cache


class Product:
    def __init__(
        self,
        sku: str | int,
        name: str,
        category: str,
        cost_price: float,
        selling_price: float,
        quantity: int,
        reorder_level: int,
    ):
        self.sku = sku
        self.name = name
        self.category = category
        self.cost_price = cost_price
        self.selling_price = selling_price
        self.quantity = quantity
        self.reorder_level = reorder_level

    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level

    def calculate_unit_profit(self) -> float:
        return self.selling_price - self.cost_price

    def calculate_inventory_value(self) -> float:
        return self.cost_price * self.quantity

class CartItem:
    def __init__(self, product: Product, quantity: int):
        self.product = product
        self.quantity = quantity

    def calculate_subtotal(self) -> float:
        return self.product.selling_price * self.quantity

class Transaction:
    def __init__(self, transaction_id: str | int, timestamp: datetime.datetime, items: list[CartItem], tax_rate: float):
        self.transaction_id = transaction_id
        self.timestamp = timestamp
        self.items = items
        self.tax_rate = tax_rate
    
    def calculate_subtotal(self) -> float:
        running_total = 0
        for item in self.items:
            running_total += item.calculate_subtotal()
        
        return running_total
    
    def calculate_tax(self) -> float:
        subtotal = self.calculate_subtotal()
        return subtotal * self.tax_rate
    
    def calculate_grand_total(self) -> float:
        subtotal = self.calculate_subtotal()
        tax = self.calculate_tax()
        return subtotal + tax