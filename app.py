import os
from typing import Any, Optional
import pandas as pd
import resend
import streamlit as st
from database import Database
from inventory_service import InventoryService
from models import SaleItem
from security_utils import generate_otp, validate_strict_password

st.set_page_config(
    page_title="Water Station Inventory Manager",
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
if "otp_store" not in st.session_state:
    st.session_state.otp_store = {}


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


def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    if not RESEND_KEY:
        st.warning("Resend API key is not configured in secrets/environment.")
        return False
    try:
        resend.Emails.send(
            params={
                "from": "Water Station Security <onboarding@resend.dev>",
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
    st.title("💧 Water Station POS & Security Portal")

    tab_login, tab_otp_login, tab_register = st.tabs(
        ["🔒 Password Login", "📧 OTP Login (Forgot Password)", "📝 Register"]
    )

    with tab_login:
        st.subheader("Welcome Back")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Log In", type="primary", use_container_width=True):
            if not username.strip() or not password.strip():
                st.error("Username and password cannot be blank.")
            else:
                user_data = db.verify_user(username, password)
                if user_data:
                    if not get_int(user_data, "is_active", 1):
                        st.error(
                            "This account has been deactivated. Contact your"
                            " administrator."
                        )
                    else:
                        st.session_state.authenticated = True
                        st.session_state.user = user_data
                        st.success(
                            f"Welcome back, {get_str(user_data, 'username')}!"
                        )
                        st.rerun()
                else:
                    st.error("Invalid username or password.")

    with tab_otp_login:
        st.subheader("Login via One-Time Password (OTP)")
        otp_user = st.text_input("Username", key="otp_user")
        user_email = st.text_input("Registered Email", key="otp_email")

        if st.button("Send Login OTP"):
            clean_user = otp_user.strip()
            clean_email = user_email.strip()
            if not clean_user or not clean_email:
                st.error("Username and email fields cannot be blank.")
            else:
                user = db.get_user_by_username(clean_user)
                if (
                    user
                    and get_str(user, "email").lower() == clean_email.lower()
                ):
                    code = generate_otp()
                    st.session_state.otp_store[clean_user] = code
                    if send_email_notification(
                        clean_email,
                        "Your Water Station Login OTP",
                        f"Your 6-digit login code is: <strong>{code}</strong>",
                    ):
                        st.success("OTP sent to your email!")
                else:
                    st.error("Username and email combination not found.")

        input_code = st.text_input("Enter 6-Digit OTP", key="input_otp")
        if st.button(
            "Verify & Log In via OTP", type="primary", use_container_width=True
        ):
            clean_user = otp_user.strip()
            if (
                clean_user in st.session_state.otp_store
                and st.session_state.otp_store[clean_user]
                == input_code.strip()
            ):
                user_data = db.get_user_by_username(clean_user)
                if user_data:
                    st.session_state.authenticated = True
                    st.session_state.user = user_data
                    st.session_state.otp_logged_in = True
                    del st.session_state.otp_store[clean_user]
                    st.success("OTP verified! Redirecting...")
                    st.rerun()
            else:
                st.error("Invalid or expired OTP.")

    with tab_register:
        st.subheader("Create Station Admin Account")
        reg_station = st.text_input("Water Station Name")
        reg_username = st.text_input("Username")
        reg_email = st.text_input("Admin Email")
        reg_password = st.text_input("Password", type="password")

        if st.button("Register Account", use_container_width=True):
            clean_station = reg_station.strip()
            clean_username = reg_username.strip()
            clean_email = reg_email.strip()
            clean_password = reg_password.strip()

            if not clean_station:
                st.error("Water Station Name cannot be blank.")
            elif not clean_username:
                st.error("Username cannot be blank.")
            elif not clean_email:
                st.error("Email cannot be blank.")
            elif not clean_password:
                st.error("Password cannot be blank.")
            elif clean_username.lower() == clean_password.lower():
                st.error("Username and Password cannot be the same.")
            else:
                is_valid, msg = validate_strict_password(
                    clean_password, username=clean_username
                )
                if not is_valid:
                    st.error(msg)
                else:
                    success, db_msg = db.create_user(
                        clean_username,
                        clean_password,
                        clean_station,
                        role="admin",
                        email=clean_email,
                    )
                    if success:
                        st.success(db_msg)
                    else:
                        st.error(db_msg)


def show_dashboard() -> None:
    current_user = st.session_state.user
    user_id = get_int(current_user, "user_id")
    station_name = get_str(current_user, "station_name", "Water Station")
    username = get_str(current_user, "username", "User")
    user_email = get_str(current_user, "email", "")
    user_role = get_str(current_user, "role", "admin")

    if st.session_state.get("otp_logged_in"):
        st.warning(
            "⚠️ You logged in via OTP. Please update your password in"
            " 'Security & Account Settings'."
        )

    with st.sidebar:
        st.title(f"💧 {station_name}")
        st.caption(f"User: **{username}** | Role: `{user_role.upper()}`")

        menu = st.radio(
            "Navigation",
            [
                "🛒 Point of Sale",
                "📦 Products & Inventory",
                "👥 Customer Retention",
                "🚚 Delivery Dispatch",
                "⚙️ Security & Account Settings",
            ],
        )

        st.divider()
        if st.button("Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.cart = []
            st.session_state.otp_logged_in = False
            st.rerun()
    
    if menu == "🛒 Point of Sale":
        st.header("🛒 Point of Sale & Checkout")

        products = inventory_svc.get_all_products(user_id=user_id)
        customers = inventory_svc.get_all_customers(user_id=user_id)

        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.subheader("Catalog")
            if not products:
                st.info("No products found. Add products in Inventory section.")
            else:
                grid_cols = st.columns(2)
                for index, prod in enumerate(products):
                    p_id = get_int(prod, "product_id")
                    p_name = get_str(prod, "name")
                    p_price = get_float(prod, "unit_price")
                    p_qty = get_int(prod, "quantity")

                    with grid_cols[index % 2]:
                        with st.container(border=True):
                            st.write(f"**{p_name}**")
                            st.write(f"Price: ₱{p_price:.2f}")
                            st.caption(f"In Stock: {p_qty} jugs")

                            if st.button(
                                "Add to Cart",
                                key=f"add_{p_id}",
                                disabled=(p_qty <= 0),
                            ):
                                st.session_state.cart.append(
                                    SaleItem(
                                        product_id=p_id,
                                        name=p_name,
                                        quantity=1,
                                        unit_price=p_price,
                                    )
                                )
                                st.rerun()

        with col_right:
            st.subheader("Current Order")

            if st.session_state.cart:
                cart_df = pd.DataFrame(
                    [
                        {
                            "Item": item.name,
                            "Qty": item.quantity,
                            "Price": f"₱{item.unit_price:.2f}",
                            "Subtotal": f"₱{item.unit_price * item.quantity:.2f}",
                        }
                        for item in st.session_state.cart
                    ]
                )
                st.dataframe(cart_df, use_container_width=True)

                total_amount = sum(
                    item.unit_price * item.quantity
                    for item in st.session_state.cart
                )
                st.markdown(f"### Total: **₱{total_amount:.2f}**")

                order_type = st.radio(
                    "Order Type",
                    ["walk_in", "delivery"],
                    format_func=lambda x: "Walk-In"
                    if x == "walk_in"
                    else "Delivery",
                )

                cust_options = {"None (Anonymous Walk-in)": None}
                for c in customers:
                    cust_options[f"{get_str(c, 'name')} ({get_str(c, 'phone')})"] = get_int(c, "customer_id")

                selected_cust_label = st.selectbox(
                    "Select Customer", list(cust_options.keys())
                )
                selected_cust_id = cust_options[selected_cust_label]

                use_prepaid = False
                if selected_cust_id:
                    use_prepaid = st.checkbox("Pay with Prepaid Credits")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Clear", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()

                with col_b2:
                    if st.button(
                        "Process Order",
                        type="primary",
                        use_container_width=True,
                    ):
                        success, msg = inventory_svc.checkout(
                            user_id=user_id,
                            cart_items=st.session_state.cart,
                            customer_id=selected_cust_id,
                            order_type=order_type,
                            use_prepaid_credits=use_prepaid,
                        )
                        if success:
                            st.success(msg)
                            st.session_state.cart = []
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                st.caption("Cart is empty.")
    
    elif menu == "📦 Products & Inventory":
        st.header("📦 Inventory Management")

        with st.expander("➕ Add New Product", expanded=False):
            with st.form("add_product_form"):
                p_name = st.text_input("Product Name")
                p_qty = st.number_input("Filled Jugs Quantity", min_value=0, value=50)
                p_empty = st.number_input("Empty Jugs Quantity", min_value=0, value=20)
                p_price = st.number_input("Unit Price (₱)", min_value=0.0, value=35.0)

                if st.form_submit_button("Save Product"):
                    if not p_name.strip():
                        st.error("Product Name cannot be blank.")
                    else:
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                INSERT INTO products (user_id, name, quantity, empty_jugs, unit_price)
                                VALUES (?, ?, ?, ?, ?)
                            """,
                                (
                                    user_id,
                                    p_name.strip(),
                                    p_qty,
                                    p_empty,
                                    p_price,
                                ),
                            )
                        st.success(f"Added '{p_name}' to inventory.")
                        st.rerun()

        st.subheader("Current Stock Levels")
        products = inventory_svc.get_all_products(user_id=user_id)
        if products:
            p_df = pd.DataFrame(products)
            st.dataframe(p_df[["name", "quantity", "empty_jugs", "unit_price"]], use_container_width=True)
        else:
            st.info("No products available.")

    elif menu == "👥 Customer Retention":
        st.header("👥 Customer Management & Loyalty")

        with st.expander("➕ Register Customer", expanded=False):
            with st.form("add_customer_form"):
                c_name = st.text_input("Full Name")
                c_phone = st.text_input("Phone Number")
                c_address = st.text_area("Delivery Address")

                if st.form_submit_button("Save Customer"):
                    if not c_name.strip():
                        st.error("Customer name is required.")
                    else:
                        inventory_svc.create_customer(
                            user_id=user_id,
                            name=c_name.strip(),
                            phone=c_phone.strip(),
                            address=c_address.strip(),
                        )
                        st.success(f"Customer '{c_name}' created!")
                        st.rerun()

        st.subheader("Customer Directory")
        customers = inventory_svc.get_all_customers(user_id=user_id)
        if customers:
            c_df = pd.DataFrame(customers)
            st.dataframe(
                c_df[["name", "phone", "address", "unreturned_jugs", "prepaid_credits"]],
                use_container_width=True,
            )
        else:
            st.info("No registered customers.")

    elif menu == "🚚 Delivery Dispatch":
        st.header("🚚 Active Delivery Dispatch")

        deliveries = inventory_svc.get_pending_deliveries(user_id=user_id)
        if deliveries:
            for d in deliveries:
                d_id = get_int(d, "delivery_id")
                sale_id = get_int(d, "sale_id")
                cust_name = get_str(d, "customer_name", "Anonymous")
                addr = get_str(d, "address", "No address")

                with st.container(border=True):
                    col_info, col_act = st.columns([3, 1])
                    with col_info:
                        st.markdown(f"**Sale #{sale_id} - {cust_name}**")
                        st.write(f"📍 Address: {addr}")
                        st.caption(f"Status: {get_str(d, 'status').upper()}")

                    with col_act:
                        if st.button("Mark Delivered", key=f"deliv_{d_id}"):
                            inventory_svc.complete_delivery(
                                delivery_id=d_id,
                                empty_returned=1,
                            )
                            st.success("Delivery completed.")
                            st.rerun()
        else:
            st.info("No active deliveries.")

    elif menu == "⚙️ Security & Account Settings":
        st.header("⚙️ Security & Account Settings")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🔑 Change Password")
            with st.form("change_password_form"):
                old_pass = st.text_input("Current Password", type="password")
                new_pass = st.text_input("New Password", type="password")
                confirm_pass = st.text_input(
                    "Confirm New Password", type="password"
                )

                if st.form_submit_button("Update Password"):
                    if not new_pass or not confirm_pass:
                        st.error("Fields cannot be empty.")
                    elif new_pass != confirm_pass:
                        st.error("New passwords do not match.")
                    else:
                        success, msg = db.change_password(
                            user_id, old_pass, new_pass
                        )
                        if success:
                            st.success(msg)
                            st.session_state.otp_logged_in = False
                        else:
                            st.error(msg)

        with col2:
            st.subheader("⚠️ Account Danger Zone")
            st.warning("Deactivating your account will disable system access.")

            if st.button("Initiate Account Deactivation"):
                code = generate_otp()
                st.session_state.deactivate_otp = code
                if user_email and send_email_notification(
                    user_email,
                    "Account Deactivation Code",
                    f"Your code is: <strong>{code}</strong>",
                ):
                    st.success(f"Deactivation OTP sent to {user_email}.")

            if "deactivate_otp" in st.session_state:
                deact_input = st.text_input("Enter Deactivation OTP")
                if st.button("Confirm Deactivation", type="primary"):
                    if (
                        deact_input.strip()
                        == st.session_state.deactivate_otp
                    ):
                        db.deactivate_user(user_id)
                        st.session_state.authenticated = False
                        st.session_state.user = None
                        st.success("Account deactivated.")
                        st.rerun()
                    else:
                        st.error("Invalid OTP.")


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


def main() -> None:
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()

if __name__ == "__main__":
    main()