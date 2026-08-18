from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

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

class SaleItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: float

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


@dataclass
class SaleItem:
    product_id: str | int
    product_name: str
    quantity: int
    unit_price: float

    @property
    def line_subtotal(self) -> float:
        return self.quantity * self.unit_price


class User(BaseModel):
    user_id: Optional[int] = None
    username: str
    password_hash: Optional[str] = None
    station_name: str = "Water Station"

class Expense(BaseModel):
    expense_id: Optional[int] = None
    user_id: int
    category: str
    amount: float
    description: Optional[str] = None
    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d")
    )


class CashFlowSummary(BaseModel):
    total_sales: float
    total_expenses: float
    net_profit: float
    cash_payments: float
    digital_payments: float = 0.0