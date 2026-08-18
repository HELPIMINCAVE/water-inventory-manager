import os
from typing import Any
import pandas as pd
import resend
import streamlit as st
from database import Database
from inventory_service import InventoryService
from models import SaleItem
from security_utils import generate_otp, validate_strict_password

# --- Page Config ---
st.set_page_config(
    page_title="Water Station Inventory Manager",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Service Integrations ---
RESEND_KEY = st.secrets.get("RESEND_API_KEY", os.getenv("RESEND_API_KEY"))
if RESEND_KEY:
    resend.api_key = str(RESEND_KEY)


@st.cache_resource
def get_services() -> tuple[Database, InventoryService]:
    database_instance = Database()
    svc = InventoryService(database_instance)
    return database_instance, svc


db, inventory_svc = get_services()

# --- Session State ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "otp_store" not in st.session_state:
    st.session_state.otp_store = {}


# --- Helpers ---
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
        st.warning("Resend API key is not configured in secrets/environment.")
        return False
    try:
        resend.Emails.send(
            {
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


# --- Authentication View ---
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
            clean_u = (username or "").strip()
            clean_p = (password or "").strip()
            if not clean_u or not clean_p:
                st.error("Username and password cannot be blank.")
            else:
                user_data = db.verify_user(clean_u, clean_p)
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
            clean_user = (otp_user or "").strip()
            clean_email = (user_email or "").strip()
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
            clean_user = (otp_user or "").strip()
            clean_code = (input_code or "").strip()
            if (
                clean_user in st.session_state.otp_store
                and st.session_state.otp_store[clean_user] == clean_code
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
            clean_station = (reg_station or "").strip()
            clean_username = (reg_username or "").strip()
            clean_email = (reg_email or "").strip()
            clean_password = (reg_password or "").strip()

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


# --- Dashboard ---
def show_dashboard() -> None:
    current_user = st.session_state.user or {}
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

    # ==========================================
    # 🛒 POINT OF SALE
    # ==========================================
    if menu == "🛒 Point of Sale":
        st.header("🛒 Point of Sale & Checkout")

        products = getattr(inventory_svc, "get_all_products", lambda user_id: [])(user_id=user_id)
        customers = getattr(inventory_svc, "get_all_customers", lambda user_id: [])(user_id=user_id)

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
                            "Product ID": item.product_id,
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
                    format_func=lambda x: "Walk-In" if x == "walk_in" else "Delivery",
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
                        checkout_fn = getattr(inventory_svc, "checkout", None)
                        if checkout_fn:
                            success, msg = checkout_fn(
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
                            st.error("Checkout process is not configured.")
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
                    clean_pname = (p_name or "").strip()
                    if not clean_pname:
                        st.error("Product Name cannot be blank.")
                    else:
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                INSERT INTO products (user_id, name, quantity, empty_quantity, unit_price)
                                VALUES (?, ?, ?, ?, ?)
                            """,
                                (
                                    user_id,
                                    clean_pname,
                                    p_qty,
                                    p_empty,
                                    p_price,
                                ),
                            )
                            conn.commit()
                        st.success(f"Added '{clean_pname}' to inventory.")
                        st.rerun()

        st.subheader("Current Stock Levels")
        products = getattr(inventory_svc, "get_all_products", lambda user_id: [])(user_id=user_id)
        if products:
            p_df = pd.DataFrame(products)
            st.dataframe(p_df, use_container_width=True)
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
                    clean_cname = (c_name or "").strip()
                    clean_cphone = (c_phone or "").strip()
                    clean_caddr = (c_address or "").strip()

                    if not clean_cname:
                        st.error("Customer name is required.")
                    else:
                        create_cust_fn = getattr(inventory_svc, "create_customer", None)
                        if create_cust_fn:
                            create_cust_fn(
                                user_id=user_id,
                                name=clean_cname,
                                phone=clean_cphone,
                                address=clean_caddr,
                            )
                        else:
                            with db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    """
                                    INSERT INTO customers (user_id, name, phone, address)
                                    VALUES (?, ?, ?, ?)
                                """,
                                    (user_id, clean_cname, clean_cphone, clean_caddr),
                                )
                                conn.commit()
                        st.success(f"Customer '{clean_cname}' created!")
                        st.rerun()

        st.subheader("Customer Directory")
        customers = getattr(inventory_svc, "get_all_customers", lambda user_id: [])(user_id=user_id)
        if customers:
            c_df = pd.DataFrame(customers)
            st.dataframe(c_df, use_container_width=True)
        else:
            st.info("No registered customers.")
    
    elif menu == "🚚 Delivery Dispatch":
        st.header("🚚 Active Delivery Dispatch")

        get_pending_fn = getattr(inventory_svc, "get_pending_deliveries", None)
        deliveries = get_pending_fn(user_id=user_id) if get_pending_fn else []

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
                            comp_fn = getattr(inventory_svc, "complete_delivery", None)
                            if comp_fn:
                                comp_fn(delivery_id=d_id, empty_returned=1)
                            st.success("Delivery completed.")
                            st.rerun()
        else:
            st.info("No active deliveries.")
    
    elif menu == "⚙️ Security & Account Settings":
        st.header("⚙️ Security & Account Settings")

        tab_reset_pass, tab_deactivate = st.tabs(
            ["🔑 Reset Password (via OTP)", "⚠️ Deactivate Account"]
        )

        with tab_reset_pass:
            st.subheader("Change Account Password")
            st.caption(
                "Must contain 8+ chars, 1 uppercase, 1 number, 1 symbol, no"
                " repeating/ordered patterns, and cannot equal username."
            )

            new_pass = st.text_input("New Password", type="password", key="reset_new_pass")
            confirm_pass = st.text_input("Confirm New Password", type="password", key="reset_conf_pass")

            if st.button("Request Confirmation OTP"):
                clean_new = (new_pass or "").strip()
                clean_conf = (confirm_pass or "").strip()

                if not clean_new:
                    st.error("New password cannot be blank.")
                elif clean_new != clean_conf:
                    st.error("Passwords do not match.")
                elif username.lower() == clean_new.lower():
                    st.error("Password cannot be the same as your username.")
                else:
                    is_valid, msg = validate_strict_password(clean_new, username=username)
                    if not is_valid:
                        st.error(msg)
                    else:
                        otp_code = generate_otp()
                        st.session_state.otp_store[f"reset_{username}"] = {
                            "code": otp_code,
                            "new_password": clean_new,
                        }
                        if user_email and send_email_notification(
                            user_email,
                            "Confirm Password Reset OTP",
                            f"Your password reset OTP is: <strong>{otp_code}</strong>",
                        ):
                            st.success("Confirmation OTP sent to your email!")

            confirm_otp = st.text_input("Enter Confirmation OTP", key="conf_reset_otp")
            if st.button("Confirm & Update Password", type="primary", use_container_width=True):
                reset_data = st.session_state.otp_store.get(f"reset_{username}")
                clean_otp = (confirm_otp or "").strip()
                if reset_data and reset_data["code"] == clean_otp:
                    success = db.update_user_password(user_id, reset_data["new_password"])
                    if success:
                        st.success("Password updated successfully! Please log in using your new credentials.")
                        st.session_state.otp_logged_in = False
                        del st.session_state.otp_store[f"reset_{username}"]
                    else:
                        st.error("Database update failed.")
                else:
                    st.error("Invalid confirmation OTP.")

        with tab_deactivate:
            st.subheader("Deactivate Account")
            st.warning("Deactivating your account disables future access for this user.")

            deact_pass = st.text_input("Current Password", type="password", key="deact_pass")

            if st.button("Request Deactivation OTP"):
                clean_deact_p = (deact_pass or "").strip()
                if not clean_deact_p:
                    st.error("Password cannot be blank.")
                else:
                    user_check = db.verify_user(username, clean_deact_p)
                    if user_check:
                        deact_otp = generate_otp()
                        st.session_state.otp_store[f"deact_{username}"] = deact_otp
                        if user_email and send_email_notification(
                            user_email,
                            "Deactivate Account OTP",
                            f"Your deactivation OTP is: <strong>{deact_otp}</strong>",
                        ):
                            st.success("Deactivation OTP sent to your email!")
                    else:
                        st.error("Incorrect password.")

            input_deact_otp = st.text_input("Enter Deactivation OTP", key="deact_otp_input")
            if st.button("Confirm Account Deactivation", type="primary", use_container_width=True):
                stored_deact_otp = st.session_state.otp_store.get(f"deact_{username}")
                clean_deact_otp = (input_deact_otp or "").strip()
                if stored_deact_otp and stored_deact_otp == clean_deact_otp:
                    db.deactivate_user_account(user_id)
                    st.success("Account deactivated.")
                    st.session_state.authenticated = False
                    st.session_state.user = None
                    st.rerun()
                else:
                    st.error("Invalid deactivation OTP.")

def main() -> None:
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()

if __name__ == "__main__":
    main()