import os
import resend
import streamlit as st
from database import Database
from inventory_service import InventoryService
from models import SaleItem


st.set_page_config(
    page_title="Water Station Inventory & Retention",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

RESEND_KEY = st.secrets.get("RESEND_API_KEY", os.getenv("RESEND_API_KEY"))
if RESEND_KEY:
    resend.api_key = RESEND_KEY


@st.cache_resource
def get_services():
    db = Database()
    svc = InventoryService(db)
    return db, svc


db, inventory_svc = get_services()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []

def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    if not RESEND_KEY:
        st.warning("Resend API key is not configured. Add RESEND_API_KEY to .streamlit/secrets.toml")
        return False
    try:
        resend.Emails.send({
            "from": "Water Station <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": f"<p>{body}</p>",
        })
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def show_auth_page():
    st.title("💧 Water Refilling Station Manager")
    
    tab_login, tab_register = st.tabs(["🔒 Log In", "📝 Register New Station"])
    
    with tab_login:
        st.subheader("Welcome Back")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("Log In", type="primary", use_container_width=True):
            user = db.authenticate_user(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.success(f"Welcome back, {user.station_name}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    
    with tab_register:
        st.subheader("Create a Station Account")
        reg_station = st.text_input("Station Name (e.g., Crystal Pure Water)")
        reg_username = st.text_input("Choose Username")
        reg_password = st.text_input("Choose Password", type="password")
        
        if st.button("Register Account", use_container_width=True):
            if reg_station and reg_username and reg_password:
                success, msg = db.create_user(reg_username, reg_password, reg_station)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Please fill out all registration fields.")

def show_dashboard():
    user = st.session_state.user
    
    with st.sidebar:
        st.title(f"💧 {user.station_name}")
        st.caption(f"Logged in as: **{user.username}**")
        
        menu = st.radio(
            "Navigation",
            [
                "🛒 Point of Sale",
                "📦 Products & Inventory",
                "👥 Customer Retention",
                "💵 Cash Flow & Expenses",
            ],
        )
        
        st.divider()
        if st.button("Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.cart = []
            st.rerun()
    
    if menu == "🛒 Point of Sale":
        st.header("🛒 Point of Sale & Checkout")
        
        col_products, col_cart = st.columns([3, 2])
        
        products = inventory_svc.get_all_products(user_id=user.user_id)
        customers = inventory_svc.get_all_customers(user_id=user.user_id)
        
        with col_products:
            st.subheader("Available Products / Services")
            if not products:
                st.info("No products found. Add products in the 'Products & Inventory' tab first.")
            else:
                for prod in products:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{prod.name}** ({prod.volume_liters}L)")
                            st.caption(f"Stock: **{prod.quantity}** available")
                        with c2:
                            st.markdown(f"**₱{prod.selling_price:.2f}**")
                        with c3:
                            qty = st.number_input(
                                "Qty",
                                min_value=1,
                                max_value=max(1, prod.quantity),
                                value=1,
                                key=f"qty_{prod.product_id}",
                            )
                            if st.button("Add", key=f"add_{prod.product_id}"):
                                st.session_state.cart.append(
                                    SaleItem(
                                        product_id=prod.product_id,
                                        product_name=prod.name,
                                        quantity=qty,
                                        unit_price=prod.selling_price,
                                    )
                                )
                                st.toast(f"Added {qty}x {prod.name} to cart!", icon="🛒")
        
        with col_cart:
            st.subheader("Current Order")
            if not st.session_state.cart:
                st.write("Cart is empty.")
            else:
                total_sum = 0.0
                for idx, item in enumerate(st.session_state.cart):
                    subtotal = item.line_subtotal
                    total_sum += subtotal
                    c_name, c_sub, c_del = st.columns([3, 2, 1])
                    c_name.write(f"{item.quantity}x {item.product_name}")
                    c_sub.write(f"₱{subtotal:.2f}")
                    if c_del.button("❌", key=f"del_{idx}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                
                st.divider()
                st.markdown(f"### Total: **₱{total_sum:.2f}**")

                cust_options = {c.customer_id: f"{c.name} ({c.phone})" for c in customers}
                cust_options[0] = "-- Walk-in Customer --"
                
                selected_cust = st.selectbox(
                    "Link to Customer (for Refill Tracking)",
                    options=list(cust_options.keys()),
                    format_func=lambda x: cust_options[x],
                )
                
                customer_id = selected_cust if selected_cust != 0 else None
                
                if st.button("Complete Transaction", type="primary", use_container_width=True):
                    success, msg = inventory_svc.checkout(
                        user_id=user.user_id,
                        cart_items=st.session_state.cart,
                        customer_id=customer_id,
                    )
                    if success:
                        st.success(msg)
                        st.session_state.cart = []
                        st.rerun()
                    else:
                        st.error(msg)
    
    elif menu == "📦 Products & Inventory":
        st.header("📦 Inventory Management")
        
        tab1, tab2 = st.tabs(["View Stock", "➕ Add New Item"])
        
        with tab1:
            products = inventory_svc.get_all_products(user_id=user.user_id)
            if products:
                prod_data = [
                    {
                        "ID": p.product_id,
                        "Product Name": p.name,
                        "Volume (L)": p.volume_liters,
                        "Cost Price": f"₱{p.cost_price:.2f}",
                        "Selling Price": f"₱{p.selling_price:.2f}",
                        "Current Stock": p.quantity,
                        "Reorder Level": p.reorder_level,
                        "Is Refill Service": "Yes" if p.is_refill_service else "No",
                    }
                    for p in products
                ]
                st.dataframe(prod_data, use_container_width=True)
            else:
                st.info("No products available.")
        
        with tab2:
            st.subheader("Add Product / Container / Refill Service")
            with st.form("add_product_form"):
                p_name = st.text_input("Item Name (e.g., 5-Gallon Slim Refill)")
                p_vol = st.number_input("Volume in Liters", min_value=0.0, value=18.9, step=0.1)
                p_cost = st.number_input("Cost Price (₱)", min_value=0.0, value=15.0, step=1.0)
                p_price = st.number_input("Selling Price (₱)", min_value=0.0, value=35.0, step=1.0)
                p_qty = st.number_input("Initial Stock Quantity", min_value=0, value=100)
                p_reorder = st.number_input("Reorder Level Alert", min_value=0, value=15)
                p_is_refill = st.checkbox("Is this a refill service?", value=True)
                
                submitted = st.form_submit_button("Save Item")
                if submitted:
                    if p_name:
                        db.add_product(
                            user_id=user.user_id,
                            name=p_name,
                            volume_liters=p_vol,
                            cost_price=p_cost,
                            selling_price=p_price,
                            quantity=p_qty,
                            reorder_level=p_reorder,
                            is_refill_service=p_is_refill,
                        )
                        st.success(f"Added '{p_name}' successfully!")
                        st.rerun()
                    else:
                        st.error("Please enter an item name.")
    
    elif menu == "👥 Customer Retention":
        st.header("👥 Retention Alerts & Refill Schedules")
        
        tab_alerts, tab_customers, tab_add = st.tabs(
            ["⚠️ Overdue Refill Alerts", "All Customers", "➕ Register Customer"]
        )
        
        with tab_alerts:
            alerts = inventory_svc.get_overdue_refill_customers(user_id=user.user_id)
            if not alerts:
                st.success("🎉 All regular customers are up-to-date with their refill schedules!")
            else:
                st.warning(f"Found {len(alerts)} customer(s) past their regular refill interval.")
                for alert in alerts:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{alert.customer_name}** ({alert.phone})")
                            st.caption(f"Normal refill cycle: every **{alert.avg_interval_days}** days")
                        with c2:
                            st.error(f"**{alert.days_since_last_refill} days** since last refill")
                        with c3:
                            email = st.text_input("Send Reminder Email", placeholder="customer@email.com",
                                                  key=f"email_{alert.customer_id}")
                            if st.button("📧 Send Reminder", key=f"btn_remind_{alert.customer_id}"):
                                if email:
                                    subject = f"Time for a refill from {user.station_name}! 💧"
                                    body = f"Hi {alert.customer_name}, it has been {alert.days_since_last_refill} days since your last water refill! Reply or call us to schedule delivery."
                                    if send_email_notification(email, subject, body):
                                        st.success("Reminder email sent!")
                                else:
                                    st.warning("Please enter an email address.")
        
        with tab_customers:
            customers = inventory_svc.get_all_customers(user_id=user.user_id)
            if customers:
                c_data = [
                    {
                        "ID": c.customer_id,
                        "Name": c.name,
                        "Phone": c.phone,
                        "Address": c.address,
                        "Expected Refill Interval": f"Every {c.average_refill_interval_days} days",
                    }
                    for c in customers
                ]
                st.dataframe(c_data, use_container_width=True)
            else:
                st.info("No customers registered yet.")
        
        with tab_add:
            st.subheader("Register Regular Customer")
            with st.form("add_customer_form"):
                c_name = st.text_input("Customer Name")
                c_phone = st.text_input("Phone Number")
                c_address = st.text_area("Delivery Address")
                c_interval = st.number_input("Expected Refill Cycle (Days)", min_value=1, value=7)
                
                c_submitted = st.form_submit_button("Register Customer")
                if c_submitted:
                    if c_name and c_phone:
                        db.add_customer(
                            user_id=user.user_id,
                            name=c_name,
                            phone=c_phone,
                            address=c_address,
                            avg_interval_days=c_interval,
                        )
                        st.success(f"Registered customer '{c_name}'!")
                        st.rerun()
                    else:
                        st.error("Name and Phone number are required.")
    
    elif menu == "💵 Cash Flow & Expenses":
        st.header("💵 Cash Flow & Operational Expenses")
        
        summary = db.get_cash_flow_totals(user_id=user.user_id)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Sales Revenue", f"₱{summary.total_sales:.2f}")
        m2.metric("Total Expenses", f"₱{summary.total_expenses:.2f}")
        m3.metric("Net Profit", f"₱{summary.net_profit:.2f}", delta=f"{summary.net_profit:.2f}")
        
        st.divider()
        st.subheader("Record Operational Expense")
        with st.form("expense_form"):
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                category = st.selectbox(
                    "Expense Category",
                    ["Water Supply / Deep Well Fee", "Electricity / Power", "Fuel / Delivery", "Maintenance & Filters",
                     "Staff Salaries", "Misc"],
                )
                amount = st.number_input("Amount (₱)", min_value=0.0, value=100.0, step=10.0)
            with col_exp2:
                description = st.text_area("Description / Notes")
            
            exp_submitted = st.form_submit_button("Record Expense")
            if exp_submitted:
                if amount > 0:
                    db.record_expense(
                        user_id=user.user_id,
                        category=category,
                        amount=amount,
                        description=description,
                    )
                    st.success(f"Recorded expense of ₱{amount:.2f} under {category}.")
                    st.rerun()
                else:
                    st.error("Expense amount must be greater than zero.")

if __name__ == "__main__":
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()