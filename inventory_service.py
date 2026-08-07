import sqlite3
from typing import Any, List, Optional, Tuple


class InventoryService:

    def __init__(self, db: Any):
        self.db = db

    def get_all_products(
        self, user_id: Optional[int] = None
    ) -> List[dict[str, Any]]:
        if user_id is None:
            return []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM products WHERE user_id = ?", (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_customers(
        self, user_id: Optional[int] = None
    ) -> List[dict[str, Any]]:
        if user_id is None:
            return []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM customers WHERE user_id = ?", (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_overdue_refill_customers(
        self, user_id: Optional[int] = None
    ) -> List[dict[str, Any]]:
        if user_id is None:
            return []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *,
                       CAST(julianday('now') - julianday(last_refill_date) AS INTEGER) AS days_since_last_refill,
                       name AS customer_name
                FROM customers
                WHERE user_id = ? AND (julianday('now') - julianday(last_refill_date)) > avg_interval_days
            """,
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def checkout(
        self,
        user_id: int,
        cart_items: List[Any],
        customer_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        if not cart_items:
            return False, "Cart is empty."

        total_amount = sum(
            float(getattr(item, "line_subtotal", 0.0)) for item in cart_items
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sales (user_id, customer_id, total_amount) VALUES"
                " (?, ?, ?)",
                (user_id, customer_id, total_amount),
            )

            for item in cart_items:
                prod_id = getattr(item, "product_id", 0)
                qty = getattr(item, "quantity", 0)
                cursor.execute(
                    "UPDATE products SET quantity = quantity - ? WHERE"
                    " product_id = ?",
                    (qty, prod_id),
                )

            if customer_id:
                cursor.execute(
                    "UPDATE customers SET last_refill_date = date('now') WHERE"
                    " customer_id = ?",
                    (customer_id,),
                )

            conn.commit()

        return True, "Transaction completed successfully!"