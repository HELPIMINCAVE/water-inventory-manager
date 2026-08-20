import sqlite3, hashlib, os

class Database:
    def __init__(self, db_path="water_station.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'owner',
                    email TEXT,
                    owner_id INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    quantity INTEGER DEFAULT 0,
                    empty_quantity INTEGER DEFAULT 0,
                    unit_price REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT,
                    address TEXT,
                    prepaid_credits REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    customer_id INTEGER,
                    total_amount REAL NOT NULL,
                    order_type TEXT DEFAULT 'walk_in',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                )
            """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sale_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
            """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS deliveries (
                    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    sale_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    empty_returned INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (sale_id) REFERENCES sales(sale_id)
                )
            """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS join_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_username TEXT NOT NULL,
                    applicant_email TEXT NOT NULL,
                    password_raw TEXT NOT NULL,
                    requested_role TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """
            )
            
            
            cursor.execute("PRAGMA table_info(join_requests)")
            join_cols = [col[1] for col in cursor.fetchall()]
            if "target_owner_id" in join_cols and "owner_id" not in join_cols:
                cursor.execute("ALTER TABLE join_requests RENAME COLUMN target_owner_id TO owner_id")
            
            cursor.execute("PRAGMA table_info(products)")
            prod_cols = [col[1] for col in cursor.fetchall()]
            if "user_id" not in prod_cols:
                cursor.execute("ALTER TABLE products ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            
            cursor.execute("PRAGMA table_info(customers)")
            cust_cols = [col[1] for col in cursor.fetchall()]
            if "user_id" not in cust_cols:
                cursor.execute("ALTER TABLE customers ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            
            cursor.execute("PRAGMA table_info(users)")
            user_cols = [col[1] for col in cursor.fetchall()]
            if "email" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
            if "owner_id" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN owner_id INTEGER")
            if "is_active" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            
            conn.commit()
    
    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_user(self, username: str, password_raw: str):
        hashed = self.hash_password(password_raw)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", (username, hashed))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_username(self, username: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def find_owner_by_details(self, owner_username: str, owner_email: str, station_name: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users
                WHERE LOWER(username) = LOWER(?)
                  AND LOWER(email) = LOWER(?)
                  AND LOWER(station_name) = LOWER(?)
                  AND role = 'owner'
            """, (owner_username, owner_email, station_name))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, username, password_raw, station_name, role="owner", email="", owner_id=None):
        hashed = self.hash_password(password_raw)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, station_name, role, email, owner_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (username, hashed, station_name, role, email, owner_id))
                conn.commit()
            return True, "Account created successfully!"
        except sqlite3.IntegrityError:
            return False, "Username already exists."
    
    def create_join_request(self, username, email, password_raw, role, owner_id):
        hashed = self.hash_password(password_raw)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO join_requests (applicant_username, applicant_email, applicant_password_hash, requested_role, target_owner_id)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, hashed, role, owner_id))
            conn.commit()
    
    def get_pending_requests_for_owner(self, owner_id: int) -> list[dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM join_requests
                WHERE owner_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (owner_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def process_join_request(self, request_id: int, approve: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM join_requests WHERE request_id = ?", (request_id,))
            req = cursor.fetchone()
            if not req:
                return False, "Request not found."
            
            req = dict(req)
            if approve:
                cursor.execute("SELECT station_name FROM users WHERE user_id = ?", (req["target_owner_id"],))
                owner = cursor.fetchone()
                station_name = owner["station_name"] if owner else "Water Station"
                
                cursor.execute("""
                    INSERT INTO users (username, password_hash, station_name, role, email, owner_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (req["applicant_username"], req["applicant_password_hash"], station_name, req["requested_role"],
                      req["applicant_email"], req["target_owner_id"]))
                
                cursor.execute("UPDATE join_requests SET status = 'approved' WHERE request_id = ?", (request_id,))
                conn.commit()
                return True, "Application approved and staff account created!"
            else:
                cursor.execute("UPDATE join_requests SET status = 'rejected' WHERE request_id = ?", (request_id,))
                conn.commit()
                return True, "Application rejected."
    
    def get_workforce(self, owner_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE owner_id = ? OR user_id = ?", (owner_id, owner_id))
            return [dict(r) for r in cursor.fetchall()]
    
    def update_user_role(self, user_id: int, new_role: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (new_role, user_id))
            conn.commit()
    
    def update_user_status(self, user_id: int, is_active: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
            conn.commit()
    
    def delete_user(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
    
    def update_station_name(self, owner_id: int, new_station_name: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET station_name = ? WHERE user_id = ? OR owner_id = ?",
                           (new_station_name, owner_id, owner_id))
            conn.commit()
    
    def update_username(self, user_id: int, new_username: str):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_username, user_id))
                conn.commit()
            return True, "Username updated!"
        except sqlite3.IntegrityError:
            return False, "Username already taken."
    
    def update_user_password(self, user_id: int, new_pass_raw: str):
        hashed = self.hash_password(new_pass_raw)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (hashed, user_id))
            conn.commit()
        return True
    
    def deactivate_user_account(self, user_id: int):
        self.update_user_status(user_id, 0)
    
    def update_email(self, user_id: int, new_email: str) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET email = ? WHERE user_id = ?",
                (new_email, user_id),
            )
            conn.commit()