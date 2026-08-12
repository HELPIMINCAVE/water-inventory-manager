import sqlite3
from typing import Any, Optional, Tuple


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
            cursor.execute("PRAGMA foreign_keys = ON;")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    role TEXT DEFAULT 'admin' -- admin, cashier, rider
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    name TEXT NOT NULL,
                    volume_liters REAL DEFAULT 0.0,
                    cost_price REAL DEFAULT 0.0,
                    selling_price REAL DEFAULT 0.0,
                    quantity INTEGER DEFAULT 0,
                    empty_quantity INTEGER DEFAULT 0,
                    reorder_level INTEGER DEFAULT 15,
                    is_refill_service INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT,
                    avg_interval_days INTEGER DEFAULT 7,
                    last_refill_date DATE,
                    prepaid_credits INTEGER DEFAULT 0,
                    container_deposit_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    category TEXT NOT NULL, -- Utilities, Fuel, Wages, Maintenance
                    amount REAL NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    customer_id INTEGER,
                    total_amount REAL NOT NULL,
                    order_type TEXT DEFAULT 'walk_in', -- walk_in, phone_order, delivery
                    status TEXT DEFAULT 'completed',    -- pending, dispatched, completed
                    assigned_rider_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE SET NULL,
                    FOREIGN KEY (assigned_rider_id) REFERENCES users (user_id) ON DELETE SET NULL
                )
            """)

            self._apply_migrations(cursor)
            conn.commit()

    def _apply_migrations(self, cursor: sqlite3.Cursor) -> None:
        migrations = [
            ("users", "role", "TEXT DEFAULT 'admin'"),
            ("products", "empty_quantity", "INTEGER DEFAULT 0"),
            ("customers", "prepaid_credits", "INTEGER DEFAULT 0"),
            ("customers", "container_deposit_count", "INTEGER DEFAULT 0"),
            ("sales", "order_type", "TEXT DEFAULT 'walk_in'"),
            ("sales", "status", "TEXT DEFAULT 'completed'"),
            ("sales", "assigned_rider_id", "INTEGER"),
        ]

        for table, column, col_def in migrations:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [c[1] for c in cursor.fetchall()]
            if column not in columns:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_def};"
                )

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
            return dict(row) if row else None

    def create_user(
        self,
        username: str,
        password: str,
        station_name: str,
        role: str = "cashier",
    ) -> Tuple[bool, str]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password, station_name, role)"
                    " VALUES (?, ?, ?, ?)",
                    (username, password, station_name, role),
                )
                conn.commit()
                return True, f"User '{username}' ({role}) created successfully!"
        except sqlite3.IntegrityError:
            return False, "Username already exists."

    def get_staff_list(self, user_id: int) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, role FROM users WHERE station_name"
                " = (SELECT station_name FROM users WHERE user_id = ?)",
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_customer_credits(
        self, customer_id: int, credits_to_add: int, deposit_change: int
    ) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE customers
                SET prepaid_credits = prepaid_credits + ?,
                    container_deposit_count = container_deposit_count + ?
                WHERE customer_id = ?
            """,
                (credits_to_add, deposit_change, customer_id),
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
                "INSERT INTO expenses (user_id, category, amount, description)"
                " VALUES (?, ?, ?, ?)",
                (user_id, category, amount, description),
            )
            conn.commit()