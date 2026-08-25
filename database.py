import sqlite3
import hashlib
from typing import Optional, List, Dict, Tuple


class Database:
    def __init__(self, db_path: str = "water_station.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'owner',
                    owner_id INTEGER DEFAULT NULL,
                    email TEXT DEFAULT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'Refill',
                    unit_price REAL NOT NULL,
                    quantity INTEGER DEFAULT 0,
                    empty_quantity INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT DEFAULT '',
                    address TEXT DEFAULT '',
                    prepaid_credits REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    customer_id INTEGER DEFAULT NULL,
                    total_amount REAL NOT NULL,
                    order_type TEXT DEFAULT 'walk_in',
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deliveries (
                    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    sale_id INTEGER NOT NULL,
                    customer_id INTEGER DEFAULT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP DEFAULT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS join_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_username TEXT NOT NULL,
                    applicant_email TEXT NOT NULL,
                    applicant_password_hash TEXT NOT NULL,
                    requested_role TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """)
            
            
            cursor.execute("PRAGMA table_info(products)")
            prod_cols = [col[1] for col in cursor.fetchall()]
            if "category" not in prod_cols:
                cursor.execute("ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'Refill'")
            if "empty_quantity" not in prod_cols:
                cursor.execute("ALTER TABLE products ADD COLUMN empty_quantity INTEGER DEFAULT 0")
            
            cursor.execute("PRAGMA table_info(sales)")
            sales_cols = [col[1] for col in cursor.fetchall()]
            if "created_at" not in sales_cols:
                cursor.execute("ALTER TABLE sales ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            
            cursor.execute("PRAGMA table_info(deliveries)")
            deliv_cols = [col[1] for col in cursor.fetchall()]
            if "created_at" not in deliv_cols:
                cursor.execute("ALTER TABLE deliveries ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            if "completed_at" not in deliv_cols:
                cursor.execute("ALTER TABLE deliveries ADD COLUMN completed_at TIMESTAMP DEFAULT NULL")
            
            conn.commit()
    
    
    def verify_user(self, username: str, password_raw: str) -> Optional[Dict]:
        pw_hash = self._hash_password(password_raw)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND password_hash = ?",
                (username, pw_hash)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, username: str, password_raw: str, station_name: str, role: str = "owner",
                    owner_id: Optional[int] = None, email: Optional[str] = None) -> Tuple[bool, str]:
        pw_hash = self._hash_password(password_raw)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, station_name, role, owner_id, email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (username, pw_hash, station_name, role, owner_id, email)
                )
                conn.commit()
            return True, "User successfully registered!"
        except sqlite3.IntegrityError:
            return False, "Username already exists. Please pick a different one."
    
    def find_owner_by_details(self, owner_username: str, owner_email: str, station_name: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM users
                WHERE username = ? AND email = ? AND LOWER(station_name) = LOWER(?) AND role = 'owner'
                """,
                (owner_username, owner_email, station_name)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    
    def create_join_request(self, username: str, email: str, password_raw: str, role: str, owner_id: int) -> bool:
        pw_hash = self._hash_password(password_raw)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO join_requests (applicant_username, applicant_email, applicant_password_hash, requested_role, owner_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, pw_hash, role, owner_id)
            )
            conn.commit()
        return True
    
    def get_pending_requests_for_owner(self, owner_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM join_requests WHERE owner_id = ? AND status = 'pending' ORDER BY created_at DESC",
                (owner_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def process_join_request(self, request_id: int, approve: bool) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM join_requests WHERE request_id = ?", (request_id,))
            req = cursor.fetchone()
            if not req:
                return False
            
            if approve:
                cursor.execute("SELECT station_name FROM users WHERE user_id = ?", (req["owner_id"],))
                owner = cursor.fetchone()
                station_name = owner["station_name"] if owner else "Water Station"
                
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, station_name, role, owner_id, email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        req["applicant_username"],
                        req["applicant_password_hash"],
                        station_name,
                        req["requested_role"],
                        req["owner_id"],
                        req["applicant_email"]
                    )
                )
                cursor.execute("UPDATE join_requests SET status = 'approved' WHERE request_id = ?", (request_id,))
            else:
                cursor.execute("UPDATE join_requests SET status = 'rejected' WHERE request_id = ?", (request_id,))
            
            conn.commit()
        return True
    
    def get_workforce(self, owner_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, email, role, is_active, created_at FROM users WHERE owner_id = ?",
                (owner_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    
    def get_sales_report(self, owner_id: int, days: int = 7) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    DATE(s.created_at) as sale_date,
                    COUNT(s.sale_id) as total_orders,
                    SUM(s.total_amount) as total_revenue
                FROM sales s
                WHERE s.user_id = ? AND s.created_at >= DATE('now', '-' || ? || ' days')
                GROUP BY DATE(s.created_at)
                ORDER BY sale_date DESC
                """,
                (owner_id, days)
            )
            return [dict(row) for row in cursor.fetchall()]