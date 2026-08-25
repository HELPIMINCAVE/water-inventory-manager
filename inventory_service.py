import sqlite3
from typing import Tuple, List, Dict, Optional

class InventoryService:
    def __init__(self, db):
        self.db = db
    
    def get_all_products(self, user_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM products WHERE user_id = ? ORDER BY product_id DESC",
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def create_product(self, user_id: int, name: str, category: str, price: float, quantity: int,
                       empty_quantity: int = 0) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(products)")
            cols = [col[1] for col in cursor.fetchall()]
            if "category" not in cols:
                cursor.execute("ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'Refill'")
            if "empty_quantity" not in cols:
                cursor.execute("ALTER TABLE products ADD COLUMN empty_quantity INTEGER DEFAULT 0")
            
            cursor.execute(
                """
                INSERT INTO products (user_id, name, category, unit_price, quantity, empty_quantity)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, name, category, float(price), max(0, int(quantity)), max(0, int(empty_quantity)))
            )
            conn.commit()
        return True
    
    def update_product(self, product_id: int, user_id: int, name: str, category: str, price: float, quantity: int,
                       empty_quantity: int) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE products
                SET name = ?, category = ?, unit_price = ?, quantity = ?, empty_quantity = ?
                WHERE product_id = ? AND user_id = ?
                """,
                (name, category, float(price), max(0, int(quantity)), max(0, int(empty_quantity)), product_id, user_id)
            )
            conn.commit()
        return True
    
    def checkout(self, user_id: int, cart_items: List[Dict], customer_id: Optional[int] = None,
                 order_type: str = "walk_in", use_prepaid_credits: bool = False) -> Tuple[bool, str]:
        if not cart_items:
            return False, "Cart is currently empty."
        
        total_amount = sum(item["subtotal"] for item in cart_items)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            for item in cart_items:
                cursor.execute(
                    "SELECT name, quantity FROM products WHERE product_id = ? AND user_id = ?",
                    (item["product_id"], user_id)
                )
                prod = cursor.fetchone()
                if not prod:
                    return False, f"Product '{item['name']}' not found in inventory."
                
                if prod["quantity"] < item["quantity"]:
                    return False, f"Insufficient stock for '{prod['name']}'. Available: {prod['quantity']}, Requested: {item['quantity']}."
            
            if customer_id and use_prepaid_credits:
                cursor.execute("SELECT prepaid_credits FROM customers WHERE customer_id = ?", (customer_id,))
                cust = cursor.fetchone()
                if not cust or cust["prepaid_credits"] < total_amount:
                    return False, f"Insufficient prepaid credits. Required: ₱{total_amount:.2f}, Balance: ₱{cust['prepaid_credits'] if cust else 0:.2f}."
                
                cursor.execute(
                    "UPDATE customers SET prepaid_credits = prepaid_credits - ? WHERE customer_id = ?",
                    (total_amount, customer_id)
                )
            
            for item in cart_items:
                cursor.execute(
                    """
                    UPDATE products
                    SET quantity = MAX(0, quantity - ?)
                    WHERE product_id = ? AND user_id = ?
                    """,
                    (item["quantity"], item["product_id"], user_id)
                )
            
            cursor.execute(
                """
                INSERT INTO sales (user_id, customer_id, total_amount, order_type, status, created_at)
                VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
                """,
                (user_id, customer_id, total_amount, order_type)
            )
            sale_id = cursor.lastrowid
            
            if order_type == "delivery":
                cursor.execute(
                    """
                    INSERT INTO deliveries (user_id, sale_id, customer_id, status, created_at)
                    VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                    """,
                    (user_id, sale_id, customer_id)
                )
            
            conn.commit()
        
        return True, f"Transaction successfully recorded! Order Total: ₱{total_amount:.2f}"
    
    def get_all_customers(self, user_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customers WHERE user_id = ? ORDER BY customer_id DESC", (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def create_customer(self, user_id: int, name: str, phone: str = "", address: str = "") -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO customers (user_id, name, phone, address) VALUES (?, ?, ?, ?)",
                (user_id, name, phone, address)
            )
            conn.commit()
        return True
    
    def get_pending_deliveries(self, user_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    d.delivery_id, d.sale_id, d.status, d.created_at,
                    c.name as customer_name, c.address, c.phone
                FROM deliveries d
                LEFT JOIN customers c ON d.customer_id = c.customer_id
                WHERE d.user_id = ? AND d.status = 'pending'
                ORDER BY d.created_at ASC
                """,
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def complete_delivery(self, delivery_id: int, empty_returned: int = 0) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE deliveries
                SET status = 'delivered', completed_at = CURRENT_TIMESTAMP
                WHERE delivery_id = ?
                """,
                (delivery_id,)
            )
            conn.commit()
        return True