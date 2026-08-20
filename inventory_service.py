import sqlite3
from typing import Any, List, Optional, Tuple

class InventoryService:
    def __init__(self, db: Any) -> None:
        self.db = db

    def get_all_products(self, user_id: int) -> List[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM products WHERE user_id = ? ORDER BY name ASC",
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_all_customers(self, user_id: int) -> List[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM customers WHERE user_id = ? ORDER BY name ASC",
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def create_customer(
        self,
        user_id: int,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
    ) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO customers (user_id, name, phone, address, prepaid_credits)
                VALUES (?, ?, ?, ?, 0.0)
            """,
                (user_id, name, phone, address),
            )
            conn.commit()
            return True

    def checkout(
        self,
        user_id: int,
        cart_items: List[Any],
        customer_id: Optional[int] = None,
        order_type: str = "walk_in",
        use_prepaid_credits: bool = False,
    ) -> Tuple[bool, str]:
        if not cart_items:
            return False, "Cart is empty."

        total_amount = 0.0
        parsed_items = []

        for item in cart_items:
            p_id = (
                item.get("product_id")
                if isinstance(item, dict)
                else getattr(item, "product_id", None)
            )
            qty = (
                item.get("quantity")
                if isinstance(item, dict)
                else getattr(item, "quantity", 1)
            )
            price = (
                item.get("unit_price")
                if isinstance(item, dict)
                else getattr(item, "unit_price", 0.0)
            )

            if p_id is None:
                continue

            subtotal = float(price) * int(qty)
            total_amount += subtotal
            parsed_items.append(
                {
                    "product_id": int(p_id),
                    "quantity": int(qty),
                    "unit_price": float(price),
                }
            )

        if not parsed_items:
            return False, "No valid items in cart."

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                for item in parsed_items:
                    cursor.execute(
                        "SELECT quantity FROM products WHERE product_id = ? AND user_id = ?",
                        (item["product_id"], user_id),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False, f"Product ID {item['product_id']} not found."
                    if row["quantity"] < item["quantity"]:
                        return (
                            False,
                            f"Insufficient stock for product ID {item['product_id']}.",
                        )

                if customer_id and use_prepaid_credits:
                    cursor.execute(
                        "SELECT prepaid_credits FROM customers WHERE customer_id = ?",
                        (customer_id,),
                    )
                    cust_row = cursor.fetchone()
                    if not cust_row or cust_row["prepaid_credits"] < total_amount:
                        return False, "Insufficient prepaid credits."

                    cursor.execute(
                        "UPDATE customers SET prepaid_credits = prepaid_credits - ? WHERE customer_id = ?",
                        (total_amount, customer_id),
                    )

                cursor.execute(
                    """
                    INSERT INTO sales (user_id, customer_id, total_amount, order_type)
                    VALUES (?, ?, ?, ?)
                """,
                    (user_id, customer_id, total_amount, order_type),
                )
                sale_id = cursor.lastrowid

                for item in parsed_items:
                    cursor.execute(
                        """
                        INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            sale_id,
                            item["product_id"],
                            item["quantity"],
                            item["unit_price"],
                        ),
                    )

                    cursor.execute(
                        """
                        UPDATE products
                        SET quantity = quantity - ?
                        WHERE product_id = ?
                    """,
                        (item["quantity"], item["product_id"]),
                    )

                if order_type == "delivery":
                    cursor.execute(
                        """
                        INSERT INTO deliveries (user_id, sale_id, status, empty_returned)
                        VALUES (?, ?, 'pending', 0)
                    """,
                        (user_id, sale_id),
                    )

                conn.commit()
                return True, f"Order processed successfully! (Sale #{sale_id})"

        except sqlite3.Error as e:
            return False, f"Database error during checkout: {str(e)}"

    def get_pending_deliveries(self, user_id: int) -> List[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    d.delivery_id,
                    d.sale_id,
                    d.status,
                    c.name as customer_name,
                    c.address
                FROM deliveries d
                JOIN sales s ON d.sale_id = s.sale_id
                LEFT JOIN customers c ON s.customer_id = c.customer_id
                WHERE d.user_id = ? AND d.status = 'pending'
                ORDER BY d.created_at DESC
            """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def complete_delivery(self, delivery_id: int, empty_returned: int = 0) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE deliveries
                SET status = 'delivered', empty_returned = ?
                WHERE delivery_id = ?
            """,
                (empty_returned, delivery_id),
            )
            conn.commit()
            return True