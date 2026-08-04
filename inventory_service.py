import uuid, hashlib
from database import *
from models import *

def generate_id(prefix: str, length: int = 6) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:length].upper()}"

class InventoryService:
    def __init__(self, db: Database):
        self.db = db

    def register_product(
        self, name: str, volume_liters: float, cost_price: float, selling_price: float, quantity: int, reorder_level: int = 10, is_refill_service: bool = False) -> Product:
        product_id = generate_id("PROD")
        
        new_product = Product(
            product_id=product_id,
            name=name,
            volume_liters=volume_liters,
            cost_price=cost_price,
            selling_price=selling_price,
            quantity=quantity,
            reorder_level=reorder_level,
            is_refill_service=is_refill_service,
        )

        self.db.add_product(new_product)
        return new_product

    def get_all_products(self) -> list[Product]:
        return self.db.get_all_products()

    def get_low_stock_products(self) -> list[Product]:
        all_products = self.db.get_all_products()
        return [p for p in all_products if p.quantity <= p.reorder_level]

    def restock_product(self, product_id: str, added_quantity: int) -> bool:
        if added_quantity <= 0:
            raise ValueError("Restock quantity must be positive.")
        self.db.update_product_quantity(product_id, added_quantity)
        return True


    def register_customer(self, name: str, phone: str, address: str, avg_interval_days: int = 7) -> Customer:
        customer_id = generate_id("CUST")

        new_customer = Customer(
            customer_id=customer_id,
            name=name,
            phone=phone,
            address=address,
            last_refill_date=None,
            average_refill_interval_days=avg_interval_days,
            total_orders_placed=0,
        )

        self.db.add_customer(new_customer)
        return new_customer

    def get_all_customers(self) -> list[Customer]:
        return self.db.get_all_customers()

    def get_overdue_refill_customers(self) -> list[ReorderAlert]:
        return self.db.get_overdue_customers()

    def validate_and_checkout(self, cart_items: list[SaleItem], customer_id: str | None = None, tax_rate: float = 0.12) -> tuple[bool, str]:
        if not cart_items:
            return False, "Cart is empty."

        all_products = {p.product_id: p for p in self.db.get_all_products()}
        for item in cart_items:
            product = all_products.get(item.product_id)
            if not product:
                return False, f"Product ID {item.product_id} not found."

            if not product.is_refill_service and product.quantity < item.quantity:
                return (
                    False,
                    f"Insufficient stock for '{product.name}'. Available: {product.quantity}, Requested: {item.quantity}",
                )

        subtotal = sum(item.line_subtotal for item in cart_items)
        tax = subtotal * tax_rate
        grand_total = subtotal + tax
        transaction_id = generate_id("TXN", length=8)

        success = self.db.process_checkout(
            transaction_id=transaction_id,
            customer_id=customer_id,
            cart_items=cart_items,
            subtotal=subtotal,
            tax=tax,
            grand_total=grand_total,
        )

        if success:
            return True, f"Transaction successful! ID: {transaction_id}"
        return False, "Database error during checkout."
    
    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(
            self, username: str, password: str, station_name: str
    ) -> bool:
        pwd_hash = self.hash_password(password)
        query = "INSERT INTO users (username, password_hash, station_name) VALUES (?, ?, ?)"
        try:
            self.db.execute(query, (username, pwd_hash, station_name))
            return True
        except Exception:
            return False
    
    def authenticate_user(
            self, username: str, password: str
    ) -> Optional[User]:
        pwd_hash = self.hash_password(password)
        query = "SELECT user_id, username, password_hash, station_name FROM users WHERE username = ? AND password_hash = ?"
        row = self.db.fetch_one(query, (username, pwd_hash))
        if row:
            return User(
                user_id=row[0],
                username=row[1],
                password_hash=row[2],
                station_name=row[3],
            )
        return None
    
    def add_expense(
            self,
            user_id: int,
            category: str,
            amount: float,
            description: str = "",
    ):
        query = "INSERT INTO expenses (user_id, category, amount, description, date) VALUES (?, ?, ?, ?, DATE('now'))"
        self.db.execute(query, (user_id, category, amount, description))
    
    def get_cash_flow_summary(
            self, user_id: int, start_date: str, end_date: str
    ) -> CashFlowSummary:
        sales_query = "SELECT SUM(total_amount) FROM sales WHERE user_id = ? AND date BETWEEN ? AND ?"
        sales_res = self.db.fetch_one(sales_query, (user_id, start_date, end_date))
        total_sales = sales_res[0] if sales_res and sales_res[0] else 0.0
        
        exp_query = "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?"
        exp_res = self.db.fetch_one(exp_query, (user_id, start_date, end_date))
        total_expenses = exp_res[0] if exp_res and exp_res[0] else 0.0
        
        return CashFlowSummary(
            total_sales=total_sales,
            total_expenses=total_expenses,
            net_profit=total_sales - total_expenses,
            cash_payments=total_sales * 0.8,
            digital_payments=total_sales * 0.2,
        )