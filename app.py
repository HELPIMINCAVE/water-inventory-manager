import os
from typing import Any, Optional
import resend
import streamlit as st
from database import Database
from inventory_service import InventoryService
from models import SaleItem

st.set_page_config(
    page_title="Water Refilling Station POS & Logistics",
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


# --- Helper Functions ---
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
        st.warning("Resend API key is not configured in secrets.")
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
    st.title("💧 Water Station POS & Logistics System")

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
                    f"Welcome back, {get_str(user_data, 'username')}!"
                )
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab_register:
        st.subheader("Create a Station Account (Admin)")
        reg_station = st.text_input("Station Name (e.g., Crystal Pure Water)")
        reg_username = st.text_input("Choose Admin Username")
        reg_password = st.text_input("Choose Password", type="password")

        if st.button("Register Account", use_container_width=True):
            if reg_station and reg_username and reg_password:
                success, msg = db.create_user(
                    reg_username, reg_password, reg_station, role="admin"
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
    user_role = get_str(current_user, "role", "cashier")

    with st.sidebar:
        st.title(f"💧 {station_name}")
        st.caption(f"User: **{username}** | Role: `{user_role.upper()}`")

        if user_role == "cashier":
            menu_options = ["🛒 Point of Sale", "👥 Customer Retention"]
        elif user_role == "rider":
            menu_options = ["🚚 Delivery Dispatch"]
        else:
            menu_options = [
                "🛒 Point of Sale",
                "📦 Products & Inventory",
                "👥 Customer Retention",
                "🚚 Delivery Dispatch",
                "💵 Cash Flow & Expenses",
                "⚙️ Staff & Security",
            ]

        menu = st.radio("Navigation", menu_options)

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
        staff_members = db.get_staff_list(user_id=user_id)
        riders = [s for s in staff_members if s.get("role") == "rider"]

        with col_products:
            st.subheader("Available Products / Services")
            if not products:
                st.info("No products found. Add products in Inventory tab.")
            else:
                for prod in products:
                    prod_id = get_int(prod, "product_id")
                    prod_name = get_str(prod, "name")
                    prod_vol = get_float(prod, "volume_liters")
                    prod_price = get_float(prod, "selling_price")
                    prod_qty = get_int(prod, "quantity")
                    prod_empty = get_int(prod, "empty_quantity")

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        with c1:
                            st.markdown(f"**{prod_name}** ({prod_vol:.1f}L)")
                            st.caption(
                                f"Filled: **{prod_qty}** | Empties:"
                                f" **{prod_empty}**"
                            )
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
                                st.toast(f"Added {qty}x {prod_name}", icon="🛒")

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

                order_type = st.radio(
                    "Order Type",
                    ["walk_in", "phone_order", "delivery"],
                    format_func=lambda x: x.replace("_", " ").title(),
                    horizontal=True,
                )

                assigned_rider_id: Optional[int] = None
                if order_type == "delivery":
                    rider_opts = {0: "-- Select Rider --"}
                    for r in riders:
                        rider_opts[get_int(r, "user_id")] = get_str(
                            r, "username"
                        )
                    sel_rider = st.selectbox(
                        "Assign Delivery Rider",
                        options=list(rider_opts.keys()),
                        format_func=lambda x: rider_opts[x],
                    )
                    assigned_rider_id = sel_rider if sel_rider != 0 else None

                cust_options: dict[int, str] = {0: "-- Walk-in Customer --"}
                for c in customers:
                    cid = get_int(c, "customer_id")
                    cname = get_str(c, "name")
                    credits = get_int(c, "prepaid_credits")
                    cust_options[cid] = f"{cname} ({credits} Prepaid Credits)"

                selected_cust = st.selectbox(
                    "Link Customer",
                    options=list(cust_options.keys()),
                    format_func=lambda x: cust_options[x],
                )
                customer_id = (
                    int(selected_cust) if selected_cust != 0 else None
                )

                use_credits = False
                if customer_id:
                    use_credits = st.checkbox(
                        "Pay using Prepaid Refill Credits"
                    )

                if use_credits:
                    st.markdown("### Total: **₱0.00** (Prepaid)")
                else:
                    st.markdown(f"### Total: **₱{total_sum:.2f}**")

                if st.button(
                    "Process & Checkout",
                    type="primary",
                    use_container_width=True,
                ):
                    success, msg = inventory_svc.checkout(
                        user_id=user_id,
                        cart_items=st.session_state.cart,
                        customer_id=customer_id,
                        order_type=order_type,
                        rider_id=assigned_rider_id,
                        use_prepaid_credits=use_credits,
                    )

                    if success:
                        st.success(msg)
                        with st.expander("🧾 Print Digital Receipt", expanded=True):
                            st.markdown(f"### {station_name}")
                            st.text(f"Order Type: {order_type.upper()}")
                            st.text(f"Items Total: ₱{total_sum:.2f}")
                            st.caption("Thank you for your business!")
                        st.session_state.cart = []
                    else:
                        st.error(msg)

    elif menu == "📦 Products & Inventory":
        st.header("📦 Inventory & Container Management")

        tab1, tab2 = st.tabs(["Stock Overview", "➕ Add Product / Container"])

        with tab1:
            products = inventory_svc.get_all_products(user_id=user_id)
            if products:
                prod_data = []
                for p in products:
                    prod_data.append({
                        "ID": get_int(p, "product_id"),
                        "Product Name": get_str(p, "name"),
                        "Volume (L)": get_float(p, "volume_liters"),
                        "Selling Price": (
                            f"₱{get_float(p, 'selling_price'):.2f}"
                        ),
                        "Filled Stock": get_int(p, "quantity"),
                        "Empty Containers": get_int(p, "empty_quantity"),
                        "Reorder Level": get_int(p, "reorder_level"),
                    })
                st.dataframe(prod_data, use_container_width=True)
            else:
                st.info("No items in inventory.")

        with tab2:
            st.subheader("Add Item or Service")
            with st.form("add_product_form"):
                p_name = st.text_input(
                    "Item Name (e.g., 5-Gallon Slim Refill)"
                )
                p_vol = float(
                    st.number_input("Volume (Liters)", min_value=0.0, value=18.9)
                )
                p_cost = float(
                    st.number_input("Cost Price (₱)", min_value=0.0, value=15.0)
                )
                p_price = float(
                    st.number_input("Selling Price (₱)", min_value=0.0, value=35.0)
                )
                p_qty = int(
                    st.number_input("Filled Quantity", min_value=0, value=100)
                )
                p_empty = int(
                    st.number_input(
                        "Empty Containers On-hand", min_value=0, value=20
                    )
                )
                p_reorder = int(
                    st.number_input("Low Stock Alert Level", min_value=0, value=15)
                )

                if st.form_submit_button("Save Item"):
                    if p_name:
                        db.add_product(
                            user_id=user_id,
                            name=p_name,
                            volume_liters=p_vol,
                            cost_price=p_cost,
                            selling_price=p_price,
                            quantity=p_qty,
                            reorder_level=p_reorder,
                            is_refill_service=True,
                        )
                        st.success(f"Added '{p_name}' successfully!")
                        st.rerun()
                    else:
                        st.error("Please provide an item name.")

    elif menu == "👥 Customer Retention":
        st.header("👥 Retention Alerts & Refill Cards")

        tab_alerts, tab_customers, tab_prepaid = st.tabs(
            ["⚠️ Overdue Alerts", "Customer Directory", "💳 Refill Cards & Deposits"]
        )

        with tab_alerts:
            alerts = inventory_svc.get_overdue_refill_customers(user_id=user_id)
            if not alerts:
                st.success("🎉 All regular customers are up-to-date!")
            else:
                for alert in alerts:
                    cid = get_int(alert, "customer_id")
                    cname = get_str(alert, "customer_name")
                    days_since = get_int(alert, "days_since_last_refill")

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 2])
                        c1.markdown(f"**{cname}** ({get_str(alert, 'phone')})")
                        c2.error(f"**{days_since} days** past refill")
                        email = c3.text_input(
                            "Email Reminder", key=f"email_{cid}"
                        )
                        if c3.button("📧 Send", key=f"btn_remind_{cid}"):
                            if email:
                                if send_email_notification(
                                    email,
                                    f"Refill Reminder from {station_name}",
                                    f"Hi {cname}, it has been {days_since} days"
                                    " since your last refill!",
                                ):
                                    st.success("Reminder sent!")

        with tab_customers:
            customers = inventory_svc.get_all_customers(user_id=user_id)
            if customers:
                st.dataframe(customers, use_container_width=True)

        with tab_prepaid:
            st.subheader("Manage Prepaid Cards & Jug Deposits")
            customers = inventory_svc.get_all_customers(user_id=user_id)
            if customers:
                c_map = {
                    get_int(c, "customer_id"): get_str(c, "name")
                    for c in customers
                }
                target_c = st.selectbox(
                    "Select Customer",
                    options=list(c_map.keys()),
                    format_func=lambda x: c_map[x],
                )

                with st.form("credits_form"):
                    add_credits = int(
                        st.number_input(
                            "Add Prepaid Refill Credits", min_value=0, value=10
                        )
                    )
                    add_deposits = int(
                        st.number_input(
                            "Add Container Deposit Count", min_value=0, value=2
                        )
                    )
                    if st.form_submit_button("Update Balance"):
                        db.update_customer_credits(
                            target_c, add_credits, add_deposits
                        )
                        st.success("Customer account updated!")
                        st.rerun()

    elif menu == "🚚 Delivery Dispatch":
        st.header("🚚 Delivery Management & Route Dispatch")

        deliveries = inventory_svc.get_dispatch_deliveries(user_id=user_id)
        if deliveries:
            for d in deliveries:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 3, 2])
                    c1.markdown(
                        f"**Customer:** {d['customer_name']} ({d['phone']})"
                    )
                    c1.caption(f"📍 **Address:** {d['address']}")
                    c2.markdown(
                        f"**Status:** `{d['status'].upper()}` | Rider:"
                        f" **{d['rider_name'] or 'Unassigned'}**"
                    )
                    if d["status"] == "pending":
                        if c3.button(
                            "Mark Delivered", key=f"deliv_{d['sale_id']}"
                        ):
                            st.success("Delivery confirmed!")
                            st.rerun()
        else:
            st.info("No active delivery orders.")

    elif menu == "💵 Cash Flow & Expenses":
        st.header("💵 Financial Reports & Expenses")

        summary = db.get_cash_flow_totals(user_id=user_id)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Sales", f"₱{get_float(summary, 'total_sales'):.2f}")
        m2.metric(
            "Total Expenses", f"₱{get_float(summary, 'total_expenses'):.2f}"
        )
        m3.metric("Net Profit", f"₱{get_float(summary, 'net_profit'):.2f}")

        st.divider()
        st.subheader("Record Expense")
        with st.form("expense_form"):
            cat = st.selectbox(
                "Category", ["Utilities", "Fuel", "Wages", "Maintenance"]
            )
            amt = float(
                st.number_input("Amount (₱)", min_value=0.0, value=100.0)
            )
            desc = st.text_area("Notes")
            if st.form_submit_button("Record Expense"):
                db.record_expense(
                    user_id=user_id, category=cat, amount=amt, description=desc
                )
                st.success("Expense recorded!")
                st.rerun()

    elif menu == "⚙️ Staff & Security":
        st.header("⚙️ User Accounts & Data Security")

        tab_staff, tab_backup = st.tabs(["Manage Staff", "💾 Data Security"])

        with tab_staff:
            st.subheader("Create Sub-Account (Cashier or Rider)")
            with st.form("add_staff_form"):
                s_user = st.text_input("Username")
                s_pass = st.text_input("Password", type="password")
                s_role = st.selectbox("Role", ["cashier", "rider", "admin"])

                if st.form_submit_button("Create Account"):
                    ok, msg = db.create_user(
                        s_user, s_pass, station_name=station_name, role=s_role
                    )
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        with tab_backup:
            st.subheader("Database Backup")
            st.caption(
                "Download your local SQLite file for offsite backup safety."
            )
            if os.path.exists("water_station.db"):
                with open("water_station.db", "rb") as f:
                    st.download_button(
                        label="⬇️ Download Database Backup",
                        data=f,
                        file_name="water_station_backup.db",
                        mime="application/x-sqlite3",
                        use_container_width=True,
                    )


if __name__ == "__main__":
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()