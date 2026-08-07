import hashlib
import sqlite3
from typing import Any, List, Optional


class InventoryService:
    def __init__(self, db):
        self.db = db

    def get_all_products(
        self, user_id: Optional[int] = None
    ) -> List[sqlite3.Row]:
        if user_id is not None:
            return self.db.get_products_by_user(user_id)
        return self.db.fetch_all("SELECT * FROM products")

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def add_product(
        self, name: str, price: float, stock: int, user_id: int
    ) -> bool:
        try:
            self.db.execute(
                "INSERT INTO products (name, price, stock, user_id) VALUES (?, ?, ?, ?)",
                (name, price, stock, user_id),
            )
            return True
        except sqlite3.Error as e:
            print(f"Database error while adding product: {e}")
            return False