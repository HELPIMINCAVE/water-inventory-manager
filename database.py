import sqlite3
from contextlib import contextmanager
from typing import *
from models import *

class Database:
    def __init__(self, db_path: str = "water_station.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    station_name TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    volume_liters REAL DEFAULT 0.0,
                    cost_price REAL DEFAULT 0.0,
                    selling_price REAL DEFAULT 0.0,
                    quantity INTEGER DEFAULT 0,
                    reorder_level INTEGER DEFAULT 15,
                    is_refill_service INTEGER DEFAULT 1
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT,
                    avg_interval_days INTEGER DEFAULT 7,
                    last_refill_date DATE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    customer_id INTEGER,
                    total_amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def verify_user(
        self, username: str, password: str
    ) -> Optional[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def create_user(
        self, username: str, password: str, station_name: str
    ) -> Tuple[bool, str]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password, station_name)"
                    " VALUES (?, ?, ?)",
                    (username, password, station_name),
                )
                conn.commit()
                return True, "Registered successfully!"
        except sqlite3.IntegrityError:
            return False, "Username already exists."

    def add_product(
        self,
        user_id: int,
        name: str,
        volume_liters: float,
        cost_price: float,
        selling_price: float,
        quantity: int,
        reorder_level: int,
        is_refill_service: bool,
    ) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO products (user_id, name, volume_liters, cost_price, selling_price, quantity, reorder_level, is_refill_service)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    name,
                    volume_liters,
                    cost_price,
                    selling_price,
                    quantity,
                    reorder_level,
                    1 if is_refill_service else 0,
                ),
            )
            conn.commit()

    def add_customer(
        self,
        user_id: int,
        name: str,
        phone: str,
        address: str,
        avg_interval_days: int,
    ) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO customers (user_id, name, phone, address, avg_interval_days, last_refill_date)
                VALUES (?, ?, ?, ?, ?, date('now'))
            """,
                (user_id, name, phone, address, avg_interval_days),
            )
            conn.commit()

    def get_cash_flow_totals(self, user_id: int) -> dict[str, float]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(total_amount), 0.0) FROM sales WHERE"
                " user_id = ?",
                (user_id,),
            )
            total_sales = float(cursor.fetchone()[0])

            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0.0) FROM expenses WHERE user_id"
                " = ?",
                (user_id,),
            )
            total_expenses = float(cursor.fetchone()[0])

            return {
                "total_sales": total_sales,
                "total_expenses": total_expenses,
                "net_profit": total_sales - total_expenses,
            }

    def record_expense(
        self, user_id: int, category: str, amount: float, description: str
    ) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO expenses (user_id, category, amount, description)
                VALUES (?, ?, ?, ?)
            """,
                (user_id, category, amount, description),
            )
            conn.commit()