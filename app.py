import os
from typing import Any, Optional, cast
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
    resend.api_key = str(RESEND_KEY)


@st.cache_resource
def get_services() -> tuple[Database, InventoryService]:
    database_instance = Database()
    svc = InventoryService(database_instance)
    return database_instance, svc


db, inventory_svc = get_services()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []


def get_str(obj: Any, key: str, default: str = "") -> str:
    val = (
        obj.get(key, default)
        if isinstance(obj, dict)
        else getattr(obj, key, default)
    )
    return str(val) if val is not None else default


def get_int(obj: Any, key: str, default: int = 0) -> int:
    val = (
        obj.get(key, default)
        if isinstance(obj, dict)
        else getattr(obj, key, default)
    )
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_float(obj: Any, key: str, default: float = 0.0) -> float:
    val = (
        obj.get(key, default)
        if isinstance(obj, dict)
        else getattr(obj, key, default)
    )
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    if not RESEND_KEY:
        st.warning(
            "Resend API key is not configured. Add RESEND_API_KEY to"
            " .streamlit/secrets.toml"
        )
        return False
    try:
        resend.Emails.send(
            params={
                "from": "Water Station <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": f"<p>{body}</p>",
            }
        )
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False


def show_auth_page() -> None:
    st.title("💧 Water Refilling Station Manager")

    tab_login, tab_register = st.tabs(
        ["🔒 Log In", "📝 Register New Station"]
    )

    with tab_login:
        st.subheader("Welcome Back")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Log In", type="primary", use_container_width=True):
            user_data = db.verify_user(username, password)
            if user_data:
                st.session_state.authenticated = True
                st.session_state.user = user_data
                st.success(
                    f"Welcome back, {get_str(user_data, 'station_name')}!"
                )
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
                success, msg = db.create_user(
                    reg_username, reg_password, reg_station
                )
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Please fill out all registration fields.")


def show_dashboard() -> None:
    current_user = st.session_state.user
    user_id = get_int(current_user, "user_id")
    station_name = get_str(current_user, "station_name", "Water Station")
    username = get_str(current_user, "username", "User")

    with st.sidebar:
        st.title(f"💧 {station_name}")
        st.caption(f"Logged in as: **{username}**")

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

        products = inventory_svc.get_all_products(user_id=user_id)
        customers = inventory_svc.get_all_customers(user_id=user_id)

        with col_products:
            st.subheader("Available Products / Services")
            if not products:
                st.info(
                    "No products found. Add products in the 'Products &"
                    " Inventory' tab first."
                )
            else:
                for prod in products:
                    prod_id = get_int(prod, "product_id")
                    prod_name = get_str(prod, "name")
                    prod_vol = get_float(prod, "volume_liters")
                    prod_price = get_float(prod, "selling_price")
                    prod_qty = get_int(prod, "quantity")

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{prod_name}** ({prod_vol:.1f}L)")
                            st.caption(f"Stock: **{prod_qty}** available")
                        with c2:
                            st.markdown(f"**₱{prod_price:.2f}**")
                        with c3:
                            qty = st.number_input(
                                "Qty",
                                min_value=1,
                                max_value=max(1, prod_qty),
                                value=1,
                                key=f"qty_{prod_id}",
                            )
                            if st.button("Add", key=f"add_{prod_id}"):
                                item = SaleItem(
                                    product_id=prod_id,
                                    product_name=prod_name,
                                    quantity=qty,
                                    unit_price=prod_price,
                                )
                                st.session_state.cart.append(item)
                                st.toast(
                                    f"Added {qty}x {prod_name} to cart!",
                                    icon="🛒",
                                )

        with col_cart:
            st.subheader("Current Order")
            if not st.session_state.cart:
                st.write("Cart is empty.")
            else:
                total_sum = 0.0
                to_delete: Optional[int] = None

                for idx, item in enumerate(st.session_state.cart):
                    item_qty = get_int(item, "quantity", 1)
                    item_name = get_str(item, "product_name")
                    item_price = get_float(item, "unit_price")
                    subtotal = item_qty * item_price
                    total_sum += subtotal

                    c_name, c_sub, c_del = st.columns([3, 2, 1])
                    c_name.write(f"{item_qty}x {item_name}")
                    c_sub.write(f"₱{subtotal:.2f}")
                    if c_del.button("❌", key=f"del_{idx}"):
                        to_delete = idx

                if to_delete is not None:
                    st.session_state.cart.pop(to_delete)
                    st.rerun()

                st.divider()
                st.markdown(f"### Total: **₱{total_sum:.2f}**")

                cust_options: dict[int, str] = {0: "-- Walk-in Customer --"}
                for c in customers:
                    cid = get_int(c, "customer_id")
                    cname = get_str(c, "name")
                    cphone = get_str(c, "phone")
                    cust_options[cid] = (
                        f"{cname} ({cphone})" if cphone else cname
                    )

                selected_cust = st.selectbox(
                    "Link to Customer (for Refill Tracking)",
                    options=list(cust_options.keys()),
                    format_func=lambda x: cust_options[x],
                )

                customer_id = (
                    int(selected_cust) if selected_cust != 0 else None
                )

                if st.button(
                    "Complete Transaction",
                    type="primary",
                    use_container_width=True,
                ):
                    success, msg = inventory_svc.checkout(
                        user_id=user_id,
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
            products = inventory_svc.get_all_products(user_id=user_id)
            if products:
                prod_data = []
                for p in products:
                    prod_data.append({
                        "ID": get_int(p, "product_id"),
                        "Product Name": get_str(p, "name"),
                        "Volume (L)": get_float(p, "volume_liters"),
                        "Cost Price": f"₱{get_float(p, 'cost_price'):.2f}",
                        "Selling Price": (
                            f"₱{get_float(p, 'selling_price'):.2f}"
                        ),
                        "Current Stock": get_int(p, "quantity"),
                        "Reorder Level": get_int(p, "reorder_level"),
                        "Is Refill Service": (
                            "Yes" if get_int(p, "is_refill_service") else "No"
                        ),
                    })
                st.dataframe(prod_data, use_container_width=True)
            else:
                st.info("No products available.")

        with tab2:
            st.subheader("Add Product / Container / Refill Service")
            with st.form("add_product_form"):
                p_name = st.text_input(
                    "Item Name (e.g., 5-Gallon Slim Refill)"
                )
                p_vol = float(
                    st.number_input(
                        "Volume in Liters", min_value=0.0, value=18.9, step=0.1
                    )
                )
                p_cost = float(
                    st.number_input(
                        "Cost Price (₱)", min_value=0.0, value=15.0, step=1.0
                    )
                )
                p_price = float(
                    st.number_input(
                        "Selling Price (₱)", min_value=0.0, value=35.0, step=1.0
                    )
                )
                p_qty = int(
                    st.number_input(
                        "Initial Stock Quantity", min_value=0, value=100
                    )
                )
                p_reorder = int(
                    st.number_input(
                        "Reorder Level Alert", min_value=0, value=15
                    )
                )
                p_is_refill = bool(
                    st.checkbox("Is this a refill service?", value=True)
                )

                submitted = st.form_submit_button("Save Item")
                if submitted:
                    if p_name:
                        db.add_product(
                            user_id=user_id,
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
            alerts = inventory_svc.get_overdue_refill_customers(user_id=user_id)
            if not alerts:
                st.success(
                    "🎉 All regular customers are up-to-date with their refill"
                    " schedules!"
                )
            else:
                st.warning(
                    f"Found {len(alerts)} customer(s) past their regular refill"
                    " interval."
                )
                for alert in alerts:
                    cid = get_int(alert, "customer_id")
                    cname = get_str(alert, "customer_name")
                    cphone = get_str(alert, "phone")
                    interval = get_int(alert, "avg_interval_days")
                    days_since = get_int(alert, "days_since_last_refill")

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{cname}** ({cphone})")
                            st.caption(
                                f"Normal refill cycle: every **{interval}**"
                                " days"
                            )
                        with c2:
                            st.error(
                                f"**{days_since} days** since last refill"
                            )
                        with c3:
                            email = st.text_input(
                                "Send Reminder Email",
                                placeholder="customer@email.com",
                                key=f"email_{cid}",
                            )
                            if st.button(
                                "📧 Send Reminder", key=f"btn_remind_{cid}"
                            ):
                                if email:
                                    subject = (
                                        f"Time for a refill from {station_name}!"
                                        " 💧"
                                    )
                                    body = (
                                        f"Hi {cname}, it has been"
                                        f" {days_since} days since your last"
                                        " water refill! Reply or call us to"
                                        " schedule delivery."
                                    )
                                    if send_email_notification(
                                        email, subject, body
                                    ):
                                        st.success("Reminder email sent!")
                                else:
                                    st.warning("Please enter an email address.")

        with tab_customers:
            customers = inventory_svc.get_all_customers(user_id=user_id)
            if customers:
                c_data = []
                for c in customers:
                    c_data.append({
                        "ID": get_int(c, "customer_id"),
                        "Name": get_str(c, "name"),
                        "Phone": get_str(c, "phone"),
                        "Address": get_str(c, "address"),
                        "Expected Refill Interval": (
                            f"Every {get_int(c, 'avg_interval_days')} days"
                        ),
                    })
                st.dataframe(c_data, use_container_width=True)
            else:
                st.info("No customers registered yet.")

        with tab_add:
            st.subheader("Register Regular Customer")
            with st.form("add_customer_form"):
                c_name = st.text_input("Customer Name")
                c_phone = st.text_input("Phone Number")
                c_address = st.text_area("Delivery Address")
                c_interval = int(
                    st.number_input(
                        "Expected Refill Cycle (Days)", min_value=1, value=7
                    )
                )

                c_submitted = st.form_submit_button("Register Customer")
                if c_submitted:
                    if c_name and c_phone:
                        db.add_customer(
                            user_id=user_id,
                            name=c_name,
                            phone=c_phone,
                            address=c_address,
                            avg_interval_days=c_interval,
                        )
                        st.success(f"Registered customer '{c_name}'!")
                        st.rerun()
                    else:
                        st.error("Name and Phone number are required.")

    # --- TAB 4: Cash Flow & Expenses ---
    elif menu == "💵 Cash Flow & Expenses":
        st.header("💵 Cash Flow & Operational Expenses")

        summary = db.get_cash_flow_totals(user_id=user_id)
        total_sales = get_float(summary, "total_sales")
        total_expenses = get_float(summary, "total_expenses")
        net_profit = get_float(summary, "net_profit")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Sales Revenue", f"₱{total_sales:.2f}")
        m2.metric("Total Expenses", f"₱{total_expenses:.2f}")
        m3.metric(
            "Net Profit", f"₱{net_profit:.2f}", delta=f"{net_profit:.2f}"
        )

        st.divider()
        st.subheader("Record Operational Expense")
        with st.form("expense_form"):
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                category = st.selectbox(
                    "Expense Category",
                    [
                        "Water Supply / Deep Well Fee",
                        "Electricity / Power",
                        "Fuel / Delivery",
                        "Maintenance & Filters",
                        "Staff Salaries",
                        "Misc",
                    ],
                )
                exp_amount = float(
                    st.number_input(
                        "Amount (₱)", min_value=0.0, value=100.0, step=10.0
                    )
                )
            with col_exp2:
                description = st.text_area("Description / Notes")

            exp_submitted = st.form_submit_button("Record Expense")
            if exp_submitted:
                if exp_amount > 0:
                    db.record_expense(
                        user_id=user_id,
                        category=category,
                        amount=exp_amount,
                        description=description,
                    )
                    st.success(
                        f"Recorded expense of ₱{exp_amount:.2f} under"
                        f" {category}."
                    )
                    st.rerun()
                else:
                    st.error("Expense amount must be greater than zero.")

if __name__ == "__main__":
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()