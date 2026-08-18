import os
from typing import Any
import pandas as pd
import resend
import streamlit as st
from database import Database
from inventory_service import InventoryService
from models import SaleItem
from security_utils import generate_otp, validate_strict_password

st.set_page_config(
    page_title="Water Station Manager",
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
    val = obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    return str(val) if val is not None else default


def get_int(obj: Any, key: str, default: int = 0) -> int:
    val = obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_float(obj: Any, key: str, default: float = 0.0) -> float:
    val = obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    if not RESEND_KEY:
        st.warning("Resend API key is not configured in secrets/environment.")
        return False
    try:
        resend.Emails.send({
            "from": "Water Station Portal <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": f"<p>{body}</p>",
        })
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False


def show_auth_page() -> None:
    st.title("💧 Water Station POS & Workforce Portal")
    
    tab_login, tab_otp_login, tab_register, tab_join = st.tabs(
        ["🔒 Login", "📧 OTP Login", "🏢 Register New Business (Owner)", "🤝 Apply to Join Station"]
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
                        st.error("This account has been deactivated. Please contact your station owner or admin.")
                    else:
                        st.session_state.authenticated = True
                        st.session_state.user = user_data
                        st.success(f"Welcome back, {get_str(user_data, 'username')}!")
                        st.rerun()
                else:
                    st.error("Invalid username or password.")
    
    with tab_otp_login:
        st.subheader("Login via One-Time Password")
        st.caption("If you entered the wrong email previously, re-enter your corrected details below.")
        
        otp_user = st.text_input("Username", key="otp_user")
        user_email = st.text_input("Registered Email Address", key="otp_email")
        
        if st.button("Send Login OTP", type="primary", use_container_width=True):
            clean_user = (otp_user or "").strip()
            clean_email = (user_email or "").strip()
            
            if not clean_user or not clean_email:
                st.error("Please enter both your username and email.")
            else:
                user = db.get_user_by_username(clean_user)
                if not user:
                    st.error("Username not found.")
                elif get_str(user, "email").lower() != clean_email.lower():
                    st.warning("Email does not match our records for this username. Double-check for typos.")
                else:
                    code = generate_otp()
                    st.session_state.otp_store[clean_user] = code
                    if send_email_notification(clean_email, "Your Login OTP",
                                               f"Your OTP code is: <strong>{code}</strong>"):
                        st.success(f"OTP sent to {clean_email}!")
        
        input_code = st.text_input("Enter 6-Digit OTP", key="input_otp")
        if st.button("Verify & Log In", use_container_width=True):
            clean_user = (otp_user or "").strip()
            clean_code = (input_code or "").strip()
            
            if clean_user in st.session_state.otp_store and st.session_state.otp_store[clean_user] == clean_code:
                user_data = db.get_user_by_username(clean_user)
                if user_data:
                    st.session_state.authenticated = True
                    st.session_state.user = user_data
                    st.session_state.otp_logged_in = True
                    del st.session_state.otp_store[clean_user]
                    st.success("Verified! Logging in...")
                    st.rerun()
            else:
                st.error("Invalid or expired OTP.")
    
    with tab_register:
        st.subheader("Register a New Business (Owner Account)")
        reg_station = st.text_input("Water Station Name", key="reg_st_name")
        reg_username = st.text_input("Owner Username", key="reg_uname")
        reg_email = st.text_input("Owner Email Address", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_pass")
        
        if st.button("Create Station & Owner Account", use_container_width=True):
            clean_station = (reg_station or "").strip()
            clean_username = (reg_username or "").strip()
            clean_email = (reg_email or "").strip()
            clean_password = (reg_password or "").strip()
            
            if not clean_station or not clean_username or not clean_email or not clean_password:
                st.error("All registration fields are required.")
            else:
                is_valid, msg = validate_strict_password(clean_password, username=clean_username)
                if not is_valid:
                    st.error(msg)
                else:
                    success, db_msg = db.create_user(
                        clean_username,
                        clean_password,
                        clean_station,
                        role="owner",
                        email=clean_email
                    )
                    if success:
                        st.success("Station registered successfully! You can now log in.")
                    else:
                        st.error(db_msg)
    
    with tab_join:
        st.subheader("Apply to Join an Existing Water Station")
        st.caption(
            "Apply as an Admin, Cashier, or Delivery Driver. The Business Owner will be notified via email to approve your request.")
        
        role = st.selectbox("Desired Role", ["admin", "cashier", "delivery_driver"])
        appl_username = st.text_input("Your Desired Username", key="join_uname")
        appl_email = st.text_input("Your Email Address (Double-check for typos)", key="join_email")
        appl_password = st.text_input("Your Password", type="password", key="join_pass")
        
        st.divider()
        st.markdown("**Target Business Owner Verification**")
        target_owner_user = st.text_input("Owner Username", key="target_owner")
        target_owner_email = st.text_input("Owner Email", key="target_email")
        target_station = st.text_input("Water Station Name", key="target_station")
        
        if st.button("Submit Join Application", type="primary", use_container_width=True):
            clean_appl_u = (appl_username or "").strip()
            clean_appl_e = (appl_email or "").strip()
            clean_appl_p = (appl_password or "").strip()
            clean_own_u = (target_owner_user or "").strip()
            clean_own_e = (target_owner_email or "").strip()
            clean_st_n = (target_station or "").strip()
            
            if not clean_appl_e or "@" not in clean_appl_e:
                st.error("Please enter a valid email address.")
            else:
                owner = db.find_owner_by_details(clean_own_u, clean_own_e, clean_st_n)
                
                if not owner:
                    st.error(
                        "Business Owner details do not match. Verify the owner's username, email, and station name.")
                else:
                    is_valid, msg = validate_strict_password(clean_appl_p, username=clean_appl_u)
                    if not is_valid:
                        st.error(msg)
                    else:
                        db.create_join_request(
                            username=clean_appl_u,
                            email=clean_appl_e,
                            password_raw=clean_appl_p,
                            role=role,
                            owner_id=owner["user_id"]
                        )
                        sent = send_email_notification(
                            owner["email"],
                            "New Workforce Join Request",
                            f"User <strong>{clean_appl_u}</strong> ({clean_appl_e}) requested to join <strong>{clean_st_n}</strong> as <strong>{role.upper()}</strong>.<br>Log in to your dashboard to approve or reject this request."
                        )
                        if sent:
                            st.success(f"Application sent! Owner notified at {owner['email']}.")
                        else:
                            st.warning(
                                "Application created! The owner can approve your request directly from their workforce dashboard.")


def show_dashboard() -> None:
    current_user = st.session_state.user or {}
    user_id = get_int(current_user, "user_id")
    owner_id = get_int(current_user, "owner_id") or user_id
    station_name = get_str(current_user, "station_name", "Water Station")
    username = get_str(current_user, "username", "User")
    user_email = get_str(current_user, "email", "")
    user_role = get_str(current_user, "role", "cashier").lower()
    
    if st.session_state.get("otp_logged_in"):
        st.warning("⚠️ You logged in via OTP. Please update your password in 'Profile & Settings' if needed.")
    
    with st.sidebar:
        st.title(f"💧 {station_name}")
        st.caption(f"User: **{username}** | Role: `{user_role.upper()}`")
        
        nav_options = ["🛒 Point of Sale", "📦 Products & Inventory"]
        if user_role in ["owner", "admin"]:
            nav_options.extend(["👥 Customer Retention", "🚚 Delivery Dispatch", "🏢 Workforce & Applications"])
        elif user_role == "delivery_driver":
            nav_options = ["🚚 Delivery Dispatch"]
        
        nav_options.append("⚙️ Profile & Settings")
        menu = st.radio("Navigation", nav_options)
        
        st.divider()
        if st.button("Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.cart = []
            st.session_state.otp_logged_in = False
            st.rerun()
    
    if menu == "🛒 Point of Sale":
        st.header("🛒 Point of Sale & Checkout")
        
        products = getattr(inventory_svc, "get_all_products", lambda user_id: [])(user_id=user_id)
        customers = getattr(inventory_svc, "get_all_customers", lambda user_id: [])(user_id=user_id)
        
        col_left, col_right = st.columns([3, 2])
        
        with col_left:
            st.subheader("Catalog")
            if not products:
                st.info("No products found. Add products in the Inventory section.")
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
                            
                            if st.button("Add to Cart", key=f"add_{p_id}", disabled=(p_qty <= 0)):
                                st.session_state.cart.append({
                                    "product_id": p_id,
                                    "quantity": 1,
                                    "unit_price": p_price
                                })
                                st.rerun()
        
        with col_right:
            st.subheader("Current Order")
            
            if st.session_state.cart:
                cart_df = pd.DataFrame(
                    [
                        {
                            "Product ID": item["product_id"],
                            "Qty": item["quantity"],
                            "Price": f"₱{item['unit_price']:.2f}",
                            "Subtotal": f"₱{item['unit_price'] * item['quantity']:.2f}",
                        }
                        for item in st.session_state.cart
                    ]
                )
                st.dataframe(cart_df, use_container_width=True)
                
                total_amount = sum(item["unit_price"] * item["quantity"] for item in st.session_state.cart)
                st.markdown(f"### Total: **₱{total_amount:.2f}**")
                
                order_type = st.radio(
                    "Order Type",
                    ["walk_in", "delivery"],
                    format_func=lambda x: "Walk-In" if x == "walk_in" else "Delivery",
                )
                
                cust_options = {"None (Anonymous Walk-in)": None}
                for c in customers:
                    cust_options[f"{get_str(c, 'name')} ({get_str(c, 'phone')})"] = get_int(c, "customer_id")
                
                selected_cust_label = st.selectbox("Select Customer", list(cust_options.keys()))
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
                    if st.button("Process Order", type="primary", use_container_width=True):
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
                                (user_id, clean_pname, p_qty, p_empty, p_price),
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
                            create_cust_fn(user_id=user_id, name=clean_cname, phone=clean_cphone, address=clean_caddr)
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
    
    elif menu == "🏢 Workforce & Applications":
        st.header("🏢 Workforce & Staff Management")
        
        tab_staff, tab_reqs = st.tabs(["👥 Current Workforce", "📩 Pending Join Applications"])
        
        with tab_staff:
            st.subheader("Manage Station Staff")
            staff_list = db.get_workforce(owner_id)
            
            for member in staff_list:
                m_id = get_int(member, "user_id")
                m_name = get_str(member, "username")
                m_role = get_str(member, "role")
                m_active = get_int(member, "is_active", 1)
                
                if m_id == user_id:
                    continue
                
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                    with col1:
                        st.markdown(f"**{m_name}**")
                        st.caption(f"Email: {get_str(member, 'email')}")
                    with col2:
                        if user_role == "owner":
                            role_opts = ["admin", "cashier", "delivery_driver"]
                            curr_idx = role_opts.index(m_role) if m_role in role_opts else 1
                            new_r = st.selectbox("Role", role_opts, index=curr_idx, key=f"role_{m_id}")
                            if new_r != m_role:
                                db.update_user_role(m_id, new_r)
                                st.success(f"Updated {m_name}'s role to {new_r.upper()}")
                                st.rerun()
                        else:
                            st.write(f"Role: `{m_role.upper()}`")
                    with col3:
                        status_str = "Active" if m_active else "Deactivated"
                        st.write(f"Status: **{status_str}**")
                        if st.button("Toggle Status", key=f"act_{m_id}"):
                            db.update_user_status(m_id, 0 if m_active else 1)
                            st.rerun()
                    with col4:
                        if user_role == "owner":
                            if st.button("Remove Member", key=f"del_{m_id}", type="primary"):
                                db.delete_user(m_id)
                                st.success("Member removed.")
                                st.rerun()
        
        with tab_reqs:
            st.subheader("Join Applications")
            pending = db.get_pending_requests_for_owner(owner_id)
            
            if not pending:
                st.info("No pending join applications.")
            else:
                for req in pending:
                    req_id = get_int(req, "request_id")
                    with st.container(border=True):
                        st.markdown(
                            f"**{get_str(req, 'applicant_username')}** applying for `{get_str(req, 'requested_role').upper()}`")
                        st.caption(f"Email: {get_str(req, 'applicant_email')}")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Approve", key=f"app_{req_id}", type="primary"):
                                db.process_join_request(req_id, approve=True)
                                st.success("Approved!")
                                st.rerun()
                        with c2:
                            if st.button("Reject", key=f"rej_{req_id}"):
                                db.process_join_request(req_id, approve=False)
                                st.info("Rejected.")
                                st.rerun()
    
    elif menu == "⚙️ Profile & Settings":
        st.header("⚙️ Station & Account Settings")
        
        if user_role == "owner":
            st.subheader("🏢 Station Profile (Owner Only)")
            new_st_name = st.text_input("Water Station Name", value=station_name)
            if st.button("Update Station Name"):
                if new_st_name.strip():
                    db.update_station_name(owner_id, new_st_name.strip())
                    st.session_state.user["station_name"] = new_st_name.strip()
                    st.success("Station name updated across all staff accounts!")
                    st.rerun()
            st.divider()
        
        st.subheader("👤 User Credentials & Profile")
        
        new_uname = st.text_input("Username", value=username, key="profile_uname_input")
        if st.button("Update Username"):
            clean_un = new_uname.strip()
            if clean_un:
                ok, msg = db.update_username(user_id, clean_un)
                if ok:
                    st.session_state.user["username"] = clean_un
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        new_em = st.text_input("Email Address", value=user_email, key="profile_email_input")
        if st.button("Update Email Address"):
            clean_em = new_em.strip()
            if not clean_em or "@" not in clean_em:
                st.error("Please provide a valid email address.")
            else:
                db.update_email(user_id, clean_em)
                st.session_state.user["email"] = clean_em
                st.success("Email address updated successfully!")
                st.rerun()
        
        st.divider()
        st.subheader("🔑 Password Reset")
        new_pass = st.text_input("New Password", type="password", key="settings_new_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="settings_conf_pass")
        
        if st.button("Update Password"):
            clean_np = new_pass.strip()
            clean_cp = confirm_pass.strip()
            
            if not clean_np:
                st.error("Password cannot be blank.")
            elif clean_np != clean_cp:
                st.error("Passwords do not match.")
            else:
                is_valid, msg = validate_strict_password(clean_np, username=username)
                if not is_valid:
                    st.error(msg)
                else:
                    db.update_user_password(user_id, clean_np)
                    st.success("Password updated successfully!")


def main() -> None:
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()


if __name__ == "__main__":
    main()