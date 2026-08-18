import sqlite3, hashlib, os

class Database:
    def __init__(self, db_path="water_station.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'cashier',
                    owner_id INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS join_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_username TEXT NOT NULL,
                    applicant_email TEXT NOT NULL,
                    applicant_password_hash TEXT NOT NULL,
                    requested_role TEXT NOT NULL,
                    target_owner_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
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
    
    def get_pending_requests_for_owner(self, owner_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM join_requests WHERE target_owner_id = ? AND status = 'pending'", (owner_id,))
            return [dict(r) for r in cursor.fetchall()]
    
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