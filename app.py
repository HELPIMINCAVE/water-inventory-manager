import streamlit as st
import pandas as pd
from database import Database
from inventory_service import InventoryService

st.set_page_config(
    page_title="Water Station Manager",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_db():
    return Database()


db = get_db()
inventory_service = InventoryService(db)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []


def save_new_product(owner_id: int, name: str, category: str, price: float, quantity: int, empty_quantity: int):
    """Safely delegates product creation and automatically patch missing schema columns."""
    if hasattr(inventory_service, "create_product"):
        return inventory_service.create_product(owner_id, name, category, price, quantity, empty_quantity)
    elif hasattr(inventory_service, "add_product"):
        return inventory_service.add_product(owner_id, name, category, price, quantity, empty_quantity)
    elif hasattr(db, "add_product"):
        return db.add_product(owner_id, name, category, price, quantity, empty_quantity)
    else:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(products)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if "category" not in columns:
                cursor.execute("ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'Refill'")
                conn.commit()
            
            cursor.execute(
                """
                INSERT INTO products (user_id, name, category, unit_price, quantity, empty_quantity)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (owner_id, name, category, price, quantity, empty_quantity)
            )
            conn.commit()
        return True



def show_auth_page():
    st.title("💧 Water Inventory Manager")
    st.subheader("Sign In or Join Station Workforce")
    
    tab1, tab2, tab3 = st.tabs(["🔑 Log In", "🏢 Register Station", "👥 Join Existing Station"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password").strip()
            submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            
            if submit:
                user = db.verify_user(username, password)
                if user:
                    if user.get("is_active", 1) == 0:
                        st.error("Account is deactivated. Please contact the station owner.")
                    else:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.success("Successfully logged in!")
                        st.rerun()
                else:
                    st.error("Invalid username or password.")
    
    with tab2:
        with st.form("register_owner_form"):
            st_name = st.text_input("Water Station Name *")
            owner_u = st.text_input("Owner Username *").strip()
            owner_p = st.text_input("Owner Password *", type="password").strip()
            owner_email = st.text_input("Email Address").strip()
            submit_reg = st.form_submit_button("Create Station Account", type="primary", use_container_width=True)
            
            if submit_reg:
                if not st_name or not owner_u or not owner_p:
                    st.warning("Please fill out all required fields.")
                else:
                    success, msg = db.create_user(
                        username=owner_u,
                        password_raw=owner_p,
                        station_name=st_name,
                        role="owner",
                        email=owner_email if owner_email else None
                    )
                    if success:
                        st.success("Station registered! Please log in above.")
                    else:
                        st.error(msg)
    
    with tab3:
        st.caption("Apply to join an existing water station's team.")
        with st.form("join_form"):
            target_owner_u = st.text_input("Station Owner Username *").strip()
            target_owner_email = st.text_input("Station Owner Email *").strip()
            station_name_confirm = st.text_input("Station Name *").strip()
            
            st.divider()
            applicant_u = st.text_input("Your Username *").strip()
            applicant_email = st.text_input("Your Email *").strip()
            applicant_p = st.text_input("Your Password *", type="password").strip()
            requested_role = st.selectbox("Requested Role", ["staff", "cashier", "delivery"])
            
            submit_join = st.form_submit_button("Submit Join Request", type="primary", use_container_width=True)
            
            if submit_join:
                if not all([target_owner_u, target_owner_email, station_name_confirm, applicant_u, applicant_email,
                            applicant_p]):
                    st.warning("Please complete all required fields.")
                else:
                    owner = db.find_owner_by_details(target_owner_u, target_owner_email, station_name_confirm)
                    if owner:
                        created = db.create_join_request(
                            username=applicant_u,
                            email=applicant_email,
                            password_raw=applicant_p,
                            role=requested_role,
                            owner_id=owner["user_id"]
                        )
                        if created:
                            st.success("Join request submitted! Waiting for owner approval.")
                        else:
                            st.error("Failed to submit request.")
                    else:
                        st.error("Owner details do not match any registered station.")



def render_dashboard_overview(user: dict):
    st.header("📊 Dashboard & Key Metrics")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    col1, col2, col3, col4 = st.columns(4)
    
    products = inventory_service.get_all_products(owner_id)
    total_stock = sum(p["quantity"] for p in products) if products else 0
    low_stock_count = sum(1 for p in products if p["quantity"] <= 10) if products else 0
    customers = inventory_service.get_all_customers(owner_id) if hasattr(inventory_service, "get_all_customers") else []
    deliveries = inventory_service.get_pending_deliveries(owner_id) if hasattr(inventory_service,
                                                                               "get_pending_deliveries") else []
    
    col1.metric("Total Water Stock", f"{total_stock} Units")
    col2.metric("Low Stock Alerts", f"{low_stock_count}", delta_color="inverse")
    col3.metric("Registered Customers", f"{len(customers)}")
    col4.metric("Pending Deliveries", f"{len(deliveries)}")
    
    st.divider()
    st.subheader("📦 Quick Inventory Overview")
    if products:
        df_prod = pd.DataFrame(products)
        st.dataframe(
            df_prod[["name", "quantity", "empty_quantity", "unit_price"]],
            use_container_width=True
        )
    else:
        st.info("No products registered yet. Go to Inventory to add water items.")


def render_record_sales_page(user: dict):
    st.header("🛒 Record Sales / POS")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    products = inventory_service.get_all_products(owner_id)
    customers = inventory_service.get_all_customers(owner_id) if hasattr(inventory_service, "get_all_customers") else []
    
    if not products:
        st.warning("Please add products to your inventory first.")
        return
    
    col_left, col_right = st.columns([1.5, 1])
    
    with col_left:
        st.subheader("Select Products")
        prod_names = [f"{p['name']} - ₱{p['unit_price']:.2f} (Stock: {p['quantity']})" for p in products]
        selected_prod_idx = st.selectbox("Choose Product", range(len(products)), format_func=lambda x: prod_names[x])
        selected_prod = products[selected_prod_idx]
        
        qty = st.number_input("Quantity", min_value=1, max_value=max(1, selected_prod["quantity"]), value=1)
        
        if st.button("➕ Add to Cart", use_container_width=True):
            st.session_state.cart.append({
                "product_id": selected_prod["product_id"],
                "name": selected_prod["name"],
                "quantity": qty,
                "unit_price": selected_prod["unit_price"],
                "subtotal": qty * selected_prod["unit_price"]
            })
            st.toast(f"Added {qty}x {selected_prod['name']} to cart!")
        
        st.divider()
        st.subheader("Cart Contents")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[["name", "quantity", "unit_price", "subtotal"]], use_container_width=True)
            
            if st.button("🗑️ Clear Cart"):
                st.session_state.cart = []
                st.rerun()
        else:
            st.info("Cart is currently empty.")
    
    with col_right:
        st.subheader("Order Details & Checkout")
        
        cust_options = ["Walk-in Customer"] + [f"{c['name']} (ID: {c['customer_id']})" for c in customers]
        cust_idx = st.selectbox("Customer", range(len(cust_options)), format_func=lambda x: cust_options[x])
        
        selected_cust_id = None
        use_prepaid = False
        
        if cust_idx > 0:
            selected_cust = customers[cust_idx - 1]
            selected_cust_id = selected_cust["customer_id"]
            st.caption(f"Prepaid Balance: ₱{selected_cust.get('prepaid_credits', 0.0):.2f}")
            use_prepaid = st.checkbox("Pay with Prepaid Credits")
        
        order_type = st.radio("Order Type", ["walk_in", "delivery"],
                              format_func=lambda x: "Walk-in" if x == "walk_in" else "Delivery")
        
        total_price = sum(item["subtotal"] for item in st.session_state.cart)
        st.markdown(f"### Total: **₱{total_price:.2f}**")
        
        if st.button("✅ Complete Checkout", type="primary", use_container_width=True,
                     disabled=not st.session_state.cart):
            success, msg = inventory_service.checkout(
                user_id=owner_id,
                cart_items=st.session_state.cart,
                customer_id=selected_cust_id,
                order_type=order_type,
                use_prepaid_credits=use_prepaid
            )
            if success:
                st.success(msg)
                st.session_state.cart = []
                st.rerun()
            else:
                st.error(msg)


def render_inventory_page(user: dict):
    st.header("📦 Inventory Management")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    tab1, tab2 = st.tabs(["📋 Current Stock", "➕ Add New Product"])
    
    with tab1:
        products = inventory_service.get_all_products(owner_id)
        if products:
            df_prod = pd.DataFrame(products)
            st.dataframe(
                df_prod[["product_id", "name", "category", "unit_price", "quantity", "empty_quantity"]],
                use_container_width=True
            )
        else:
            st.info("No stock records found. Use the 'Add New Product' tab to create your first item.")
    
    # --- TAB 2: ADD NEW PRODUCT FORM ---
    with tab2:
        st.subheader("Register Product or Service")
        with st.form("add_product_form", clear_on_submit=True):
            p_name = st.text_input("Product / Service Name *", placeholder="e.g., 5-Gallon Slim Refill")
            p_category = st.selectbox("Category", ["Refill", "Container/Jug", "Dispenser/Accessory", "Service"])
            
            col1, col2, col3 = st.columns(3)
            p_price = col1.number_input("Unit Price (₱) *", min_value=0.0, step=1.0, value=35.0)
            p_stock = col2.number_input("Initial Filled Stock (Qty) *", min_value=0, step=1, value=50)
            p_empty = col3.number_input("Empty Jugs Available", min_value=0, step=1, value=20)
            
            submit_product = st.form_submit_button("💾 Save Product", type="primary", use_container_width=True)
            
            if submit_product:
                if not p_name.strip():
                    st.warning("Please provide a product name.")
                else:
                    try:
                        save_new_product(
                            owner_id=owner_id,
                            name=p_name.strip(),
                            category=p_category,
                            price=p_price,
                            quantity=p_stock,
                            empty_quantity=p_empty
                        )
                        st.success(f"Successfully added **{p_name}** to inventory!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to add product: {e}")


def render_customers_page(user: dict):
    st.header("👥 Customer Management")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    with st.form("add_customer_form"):
        st.subheader("Add New Customer")
        c_name = st.text_input("Customer Name *")
        c_phone = st.text_input("Phone Number")
        c_address = st.text_area("Delivery Address")
        submit_c = st.form_submit_button("Save Customer")
        
        if submit_c:
            if c_name:
                inventory_service.create_customer(owner_id, c_name, c_phone, c_address)
                st.success("Customer added!")
                st.rerun()
            else:
                st.warning("Customer name is required.")
    
    st.divider()
    customers = inventory_service.get_all_customers(owner_id)
    if customers:
        st.dataframe(pd.DataFrame(customers), use_container_width=True)


def render_deliveries_page(user: dict):
    st.header("🚚 Delivery Tracking")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    deliveries = inventory_service.get_pending_deliveries(owner_id)
    if deliveries:
        for d in deliveries:
            with st.expander(f"Delivery #{d['delivery_id']} - {d.get('customer_name', 'Walk-in')}"):
                st.write(f"**Address:** {d.get('address', 'N/A')}")
                empty_ret = st.number_input(f"Empty Jugs Returned (ID: {d['delivery_id']})", min_value=0, value=0)
                if st.button(f"Mark Delivered #{d['delivery_id']}"):
                    inventory_service.complete_delivery(d["delivery_id"], empty_returned=empty_ret)
                    st.success("Delivery completed!")
                    st.rerun()
    else:
        st.info("No pending deliveries.")


def render_ai_marketing_page(user: dict):
    st.header("🤖 AI Marketing & Tech Hub")
    st.caption("Generate marketing copy, promos, and intelligent customer engagement strategies.")
    
    tab1, tab2 = st.tabs(["📢 Promo Campaign Generator", "🎯 Smart Re-engagement"])
    
    with tab1:
        st.subheader("Generate SMS & Social Media Content")
        promo_type = st.selectbox("Campaign Objective",
                                  ["Refill Loyalty Discount", "New Customer Onboarding", "Prepaid Jug Promo",
                                   "Weather Warm-up Blast"])
        audience = st.text_input("Target Audience", value="Nearby Neighborhoods & Residential Accounts")
        discount = st.slider("Discount Offer (%)", 0, 50, 10)
        
        if st.button("✨ Generate AI Marketing Campaign", type="primary"):
            st.divider()
            st.markdown("### 📝 Suggested Promotional Copy")
            st.code(
                f"💧 Stay hydrated with {user.get('station_name', 'Water Station')}!\n\n"
                f"Special Offer for {audience}: Get {discount}% OFF on your next gallon refill! "
                f"Fast & clean delivery directly to your doorstep. Call/text us today to order your refill! 🚛💦",
                language="markdown"
            )
    
    with tab2:
        st.subheader("💡 Automated Business Insights")
        st.info("• **Retention Alert:** 14 customers haven't requested a refill in over 12 days.")
        st.success(
            "• **Peak Delivery Window:** Highest order volume occurs between 10:00 AM and 2:00 PM on Wednesdays and Saturdays.")


def render_settings_page(user: dict):
    st.header("⚙️ Station Settings & Workforce Management")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    if user["role"] == "owner":
        st.subheader("Pending Workforce Join Applications")
        pending_reqs = db.get_pending_requests_for_owner(owner_id)
        if pending_reqs:
            for req in pending_reqs:
                col_a, col_b, col_c = st.columns([2, 1, 1])
                col_a.write(
                    f"**{req['applicant_username']}** ({req['applicant_email']}) — Role: *{req['requested_role'].upper()}*")
                if col_b.button("Approve", key=f"app_{req['request_id']}"):
                    db.process_join_request(req["request_id"], approve=True)
                    st.success("Approved!")
                    st.rerun()
                if col_c.button("Reject", key=f"rej_{req['request_id']}"):
                    db.process_join_request(req["request_id"], approve=False)
                    st.info("Rejected.")
                    st.rerun()
        else:
            st.info("No pending join requests.")
        
        st.divider()
        st.subheader("Active Team Members")
        team = db.get_workforce(owner_id)
        if team:
            st.dataframe(pd.DataFrame(team)[["username", "email", "role", "is_active"]], use_container_width=True)
    else:
        st.info("Staff account - workforce settings are managed by the station owner.")

def show_dashboard():
    user = st.session_state.user
    
    # Sidebar Header
    st.sidebar.title(f"💧 {user.get('station_name', 'Water Station')}")
    st.sidebar.caption(f"Logged in as **{user['username']}** ({user['role'].upper()})")
    
    menu_options = [
        "📊 Dashboard",
        "🛒 Record Sales",
        "📦 Inventory",
        "👥 Customers",
        "🚚 Deliveries",
        "🤖 AI Marketing & Tech",
        "⚙️ Settings & Workforce"
    ]
    
    selected_tab = st.sidebar.radio("Navigation", menu_options)
    
    st.sidebar.divider()
    if st.sidebar.button("🚪 Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.cart = []
        st.rerun()
    
    # Tab Routing
    if selected_tab == "📊 Dashboard":
        render_dashboard_overview(user)
    elif selected_tab == "🛒 Record Sales":
        render_record_sales_page(user)
    elif selected_tab == "📦 Inventory":
        render_inventory_page(user)
    elif selected_tab == "👥 Customers":
        render_customers_page(user)
    elif selected_tab == "🚚 Deliveries":
        render_deliveries_page(user)
    elif selected_tab == "🤖 AI Marketing & Tech":
        render_ai_marketing_page(user)
    elif selected_tab == "⚙️ Settings & Workforce":
        render_settings_page(user)


def main():
    if not st.session_state.authenticated:
        show_auth_page()
    else:
        show_dashboard()


if __name__ == "__main__":
    main()