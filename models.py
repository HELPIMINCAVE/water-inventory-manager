from dataclasses import dataclass
from datetime import datetime


@dataclass
class Product:
    product_id: str | int
    name: str
    volume_liters: float
    cost_price: float
    selling_price: float
    quantity: int
    reorder_level: int
    is_refill_service: bool = True

    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level

    def calculate_unit_profit(self) -> float:
        return self.selling_price - self.cost_price


@dataclass
class Customer:
    customer_id: str | int
    name: str
    phone: str
    address: str
    last_refill_date: datetime | None = None
    average_refill_interval_days: int = 7
    total_orders_placed: int = 0


@dataclass
class ReorderAlert:
    customer_id: str | int
    customer_name: str
    phone: str
    days_since_last_refill: int
    is_overdue: bool