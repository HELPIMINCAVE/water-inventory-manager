import os
import sqlite3
from typing import Any, Optional
from werkzeug.security import check_password_hash, generate_password_hash


class Database:
    def __init__(self, db_path: str = "water_inventory.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'admin',
                    email TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    empty_quantity INTEGER NOT NULL DEFAULT 0,
                    unit_price REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    address TEXT,
                    phone TEXT,
                    prepaid_credits INTEGER NOT NULL DEFAULT 0,
                    last_refill_date TEXT,
                    avg_interval_days INTEGER NOT NULL DEFAULT 7,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    customer_id INTEGER,
                    total_amount REAL NOT NULL DEFAULT 0.0,
                    order_type TEXT NOT NULL DEFAULT 'walk_in',
                    status TEXT NOT NULL DEFAULT 'completed',
                    assigned_rider_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
                )
            """
            )

            conn.commit()

    def create_user(
        self,
        username: str,
        password: str,
        station_name: str,
        role: str = "admin",
        email: str = "",
    ) -> tuple[bool, str]:
        password_hash = generate_password_hash(password)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, station_name, role, email, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """,
                    (
                        username.strip(),
                        password_hash,
                        station_name.strip(),
                        role,
                        email.strip(),
                    ),
                )
                conn.commit()
                return True, "User successfully registered!"
        except sqlite3.IntegrityError:
            return False, "Username already exists."
        except Exception as e:
            return False, f"Database error: {e}"

    def verify_user(
        self, username: str, password: str
    ) -> Optional[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            )
            user = cursor.fetchone()
            if user and check_password_hash(user["password_hash"], password):
                return dict(user)
            return None

    def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        new_hash = generate_password_hash(new_password)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (new_hash, user_id),
            )
            conn.commit()
            return True

    def deactivate_user_account(self, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            return True