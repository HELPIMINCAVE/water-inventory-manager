from dataclasses import dataclass
from typing import Optional


@dataclass
class SaleItem:
    product_id: int
    quantity: int
    unit_price: float


@dataclass
class User:
    user_id: int
    username: str
    station_name: str
    role: str = "owner"
    email: Optional[str] = None
    owner_id: Optional[int] = None
    is_active: int = 1


@dataclass
class Product:
    product_id: int
    user_id: int
    name: str
    quantity: int = 0
    empty_quantity: int = 0
    unit_price: float = 0.0


@dataclass
class Customer:
    customer_id: int
    user_id: int
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    prepaid_credits: float = 0.0


@dataclass
class Sale:
    sale_id: int
    user_id: int
    total_amount: float
    customer_id: Optional[int] = None
    order_type: str = "walk_in"


@dataclass
class Delivery:
    delivery_id: int
    user_id: int
    sale_id: int
    status: str = "pending"
    empty_returned: int = 0