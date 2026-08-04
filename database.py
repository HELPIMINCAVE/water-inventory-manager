import sqlite3
from contextlib import contextmanager
from typing import Optional
from models import *


class Database:

    def __init__(self, db_path: str = "water_station.db"):
        self.db_path = db_path
        self._migrate_db()
    
    def _migrate_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(customers)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if columns and "created_at" not in columns:
                cursor.execute("ALTER TABLE customers ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                
            conn.commit()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def initialize_tables(self):
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    volume_liters REAL NOT NULL,
                    cost_price REAL NOT NULL,
                    selling_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    reorder_level INTEGER NOT NULL,
                    is_refill_service INTEGER NOT NULL
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    last_refill_date TEXT,
                    avg_interval_days INTEGER DEFAULT 7,
                    total_orders INTEGER DEFAULT 0
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    transaction_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    timestamp TEXT NOT NULL,
                    subtotal REAL NOT NULL,
                    tax REAL NOT NULL,
                    grand_total REAL NOT NULL,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sale_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    line_subtotal REAL NOT NULL,
                    FOREIGN KEY(transaction_id) REFERENCES sales(transaction_id),
                    FOREIGN KEY(product_id) REFERENCES products(product_id)
                )
            """
            )

    def add_product(self, product: Product):
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO products
                    (product_id, name, volume_liters, cost_price, selling_price, quantity, reorder_level, is_refill_service)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.product_id,
                    product.name,
                    product.volume_liters,
                    product.cost_price,
                    product.selling_price,
                    product.quantity,
                    product.reorder_level,
                    1 if product.is_refill_service else 0,
                ),
            )

    def get_all_products(self) -> list[Product]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM products")
            return [
                Product(
                    product_id=row["product_id"],
                    name=row["name"],
                    volume_liters=row["volume_liters"],
                    cost_price=row["cost_price"],
                    selling_price=row["selling_price"],
                    quantity=row["quantity"],
                    reorder_level=row["reorder_level"],
                    is_refill_service=bool(row["is_refill_service"]),
                )
                for row in cursor
            ]

    def update_product_quantity(self, product_id: str, delta_quantity: int):
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE products
                SET quantity = quantity + ?
                WHERE product_id = ?
                """,
                (delta_quantity, product_id),
            )

    def add_customer(self, customer: Customer):
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO customers
                    (customer_id, name, phone, address, last_refill_date, avg_interval_days, total_orders)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer.customer_id,
                    customer.name,
                    customer.phone,
                    customer.address,
                    customer.last_refill_date,
                    customer.average_refill_interval_days,
                    customer.total_orders_placed,
                ),
            )

    def get_all_customers(self) -> list[Customer]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM customers")
            return [
                Customer(
                    customer_id=row["customer_id"],
                    name=row["name"],
                    phone=row["phone"],
                    address=row["address"],
                    last_refill_date=row["last_refill_date"],
                    average_refill_interval_days=row["avg_interval_days"],
                    total_orders_placed=row["total_orders"],
                )
                for row in cursor
            ]

    def get_overdue_customers(self) -> list[ReorderAlert]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    customer_id,
                    name,
                    phone,
                    last_refill_date,
                    CAST((julianday('now') - julianday(last_refill_date)) AS INTEGER) AS days_since_last_refill,
                    avg_interval_days
                FROM customers
                WHERE last_refill_date IS NOT NULL
                  AND (julianday('now') - julianday(last_refill_date)) > avg_interval_days
            """
            )

            return [
                ReorderAlert(
                    customer_id=row["customer_id"],
                    customer_name=row["name"],
                    phone=row["phone"],
                    days_since_last_refill=row["days_since_last_refill"],
                    is_overdue=True,
                )
                for row in cursor
            ]

    def process_checkout(
        self,
        transaction_id: str,
        customer_id: Optional[str],
        cart_items: list[SaleItem],
        subtotal: float,
        tax: float,
        grand_total: float,
    ) -> bool:
        current_timestamp = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sales (transaction_id, customer_id, timestamp, subtotal, tax, grand_total)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    customer_id,
                    current_timestamp,
                    subtotal,
                    tax,
                    grand_total,
                ),
            )

            for item in cart_items:
                conn.execute(
                    """
                    INSERT INTO sale_items (transaction_id, product_id, quantity, unit_price, line_subtotal)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        transaction_id,
                        item.product_id,
                        item.quantity,
                        item.unit_price,
                        item.line_subtotal,
                    ),
                )

                conn.execute(
                    """
                    UPDATE products
                    SET quantity = quantity - ?
                    WHERE product_id = ?
                    """,
                    (item.quantity, item.product_id),
                )

            if customer_id:
                conn.execute(
                    """
                    UPDATE customers
                    SET last_refill_date = DATE('now'),
                        total_orders = total_orders + 1
                    WHERE customer_id = ?
                    """,
                    (customer_id,),
                )

        return True
    
    def verify_user(self, username, password):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM users
                WHERE username = ? AND password = ?
                """,
                (username, password),
            )
            user = cursor.fetchone()
            return user