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

    def checkout(
        self,
        user_id: int,
        cart_items: List[Any],
        customer_id: Optional[int] = None,
        order_type: str = "walk_in",
        rider_id: Optional[int] = None,
        use_prepaid_credits: bool = False,
    ) -> Tuple[bool, str]:
        if not cart_items:
            return False, "Cart is empty."

        total_amount = sum(
            float(getattr(item, "unit_price", 0.0))
            * int(getattr(item, "quantity", 1))
            for item in cart_items
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if customer_id and use_prepaid_credits:
                cursor.execute(
                    "SELECT prepaid_credits FROM customers WHERE customer_id ="
                    " ?",
                    (customer_id,),
                )
                row = cursor.fetchone()
                total_items = sum(
                    int(getattr(i, "quantity", 1)) for i in cart_items
                )
                if row and row["prepaid_credits"] >= total_items:
                    cursor.execute(
                        "UPDATE customers SET prepaid_credits = prepaid_credits"
                        " - ? WHERE customer_id = ?",
                        (total_items, customer_id),
                    )
                    total_amount = 0.0
                else:
                    return False, "Insufficient prepaid card credits."

            status = "pending" if order_type == "delivery" else "completed"

            cursor.execute(
                """
                INSERT INTO sales (user_id, customer_id, total_amount, order_type, status, assigned_rider_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    customer_id,
                    total_amount,
                    order_type,
                    status,
                    rider_id,
                ),
            )

            for item in cart_items:
                prod_id = getattr(item, "product_id", 0)
                qty = int(getattr(item, "quantity", 1))

                cursor.execute(
                    """
                    UPDATE products
                    SET quantity = quantity - ?,
                        empty_quantity = empty_quantity + ?
                    WHERE product_id = ?
                """,
                    (qty, qty, prod_id),
                )

            if customer_id:
                cursor.execute(
                    "UPDATE customers SET last_refill_date = date('now') WHERE"
                    " customer_id = ?",
                    (customer_id,),
                )

            conn.commit()

        return True, "Order successfully processed!"

    def get_dispatch_deliveries(self, user_id: int) -> List[dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.sale_id, s.total_amount, s.status, c.name as customer_name,
                       c.address, c.phone, u.username as rider_name
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.customer_id
                LEFT JOIN users u ON s.assigned_rider_id = u.user_id
                WHERE s.user_id = ? AND s.order_type = 'delivery'
                ORDER BY s.created_at DESC
            """,
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]