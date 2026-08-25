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


def show_auth_page():
    st.title("💧 Water Station Manager")
    st.caption("Point of Sale, Inventory Management & Delivery System")
    
    tab1, tab2, tab3 = st.tabs(["🔑 Log In", "🏢 Register Station", "👥 Join Workforce"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password").strip()
            submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            
            if submit:
                user = db.verify_user(username, password)
                if user:
                    if user.get("is_active", 1) == 0:
                        st.error("Account deactivated. Contact station owner.")
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
        st.caption("Apply to join an existing water station workforce.")
        with st.form("join_form"):
            target_owner_u = st.text_input("Station Owner Username *").strip()
            target_owner_email = st.text_input("Station Owner Email *").strip()
            station_name_confirm = st.text_input("Station Name *").strip()
            
            st.divider()
            applicant_u = st.text_input("Your Username *").strip()
            applicant_email = st.text_input("Your Email *").strip()
            applicant_p = st.text_input("Your Password *", type="password").strip()
            requested_role = st.selectbox("Requested Role", ["staff", "cashier", "delivery"])
            
            submit_join = st.form_submit_button("Submit Application", type="primary", use_container_width=True)
            
            if submit_join:
                if not all([target_owner_u, target_owner_email, station_name_confirm, applicant_u, applicant_email,
                            applicant_p]):
                    st.warning("Please fill in all details.")
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
                            st.success("Application submitted! Pending station owner approval.")
                        else:
                            st.error("Failed to submit application.")
                    else:
                        st.error("Station owner verification failed.")



def render_dashboard_overview(user: dict):
    st.header("📊 Dashboard & Key Metrics")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    products = inventory_service.get_all_products(owner_id)
    customers = inventory_service.get_all_customers(owner_id)
    deliveries = inventory_service.get_pending_deliveries(owner_id)
    
    total_stock = sum(p["quantity"] for p in products) if products else 0
    low_stock_count = sum(1 for p in products if p["quantity"] <= 10) if products else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Water Stock", f"{total_stock} Units")
    col2.metric("Low Stock Alerts", f"{low_stock_count}", delta_color="inverse")
    col3.metric("Registered Customers", f"{len(customers)}")
    col4.metric("Pending Deliveries", f"{len(deliveries)}")
    
    st.divider()
    st.subheader("📦 Inventory Snapshot")
    if products:
        st.dataframe(pd.DataFrame(products)[["name", "category", "unit_price", "quantity", "empty_quantity"]],
                     use_container_width=True)
    else:
        st.info("No items registered yet.")


def render_sales_reports_section(user: dict):
    st.header("📈 Weekly & Monthly Sales Reports")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    range_choice = st.radio("Select Analytics Period", ["Weekly (Last 7 Days)", "Monthly (Last 30 Days)"],
                            horizontal=True)
    days = 7 if "Weekly" in range_choice else 30
    
    if hasattr(db, "get_sales_report"):
        report_data = db.get_sales_report(owner_id, days=days)
    else:
        report_data = []
    
    if report_data:
        df = pd.DataFrame(report_data)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Period Revenue", f"₱{df['total_revenue'].sum():,.2f}")
        col2.metric("Orders Processed", f"{df['total_orders'].sum()}")
        col3.metric("Avg Daily Revenue", f"₱{df['total_revenue'].mean():,.2f}")
        
        st.divider()
        st.markdown("### Daily Sales Trend")
        st.bar_chart(df.set_index("sale_date")["total_revenue"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info(f"No completed sales recorded within the last {days} days.")


def render_record_sales_page(user: dict):
    st.header("🛒 Record Sales / POS")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    products = inventory_service.get_all_products(owner_id)
    customers = inventory_service.get_all_customers(owner_id)
    
    if not products:
        st.warning("No products found. Please add products in the Inventory tab first.")
        return
    
    col_left, col_right = st.columns([1.5, 1])
    
    with col_left:
        st.subheader("Select Products")
        prod_names = [f"{p['name']} — ₱{p['unit_price']:.2f} (Stock: {p['quantity']})" for p in products]
        selected_prod_idx = st.selectbox("Product Selection", range(len(products)), format_func=lambda x: prod_names[x])
        selected_prod = products[selected_prod_idx]
        
        qty = st.number_input("Quantity", min_value=1, max_value=max(1, selected_prod["quantity"]), value=1)
        
        if st.button("➕ Add to Cart", use_container_width=True):
            if selected_prod["quantity"] < qty:
                st.error("Cannot add more than available stock!")
            else:
                st.session_state.cart.append({
                    "product_id": selected_prod["product_id"],
                    "name": selected_prod["name"],
                    "quantity": qty,
                    "unit_price": selected_prod["unit_price"],
                    "subtotal": qty * selected_prod["unit_price"]
                })
                st.toast(f"Added {qty}x {selected_prod['name']} to cart!")
        
        st.divider()
        st.subheader("Cart Items")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[["name", "quantity", "unit_price", "subtotal"]], use_container_width=True)
            
            if st.button("🗑️ Clear Cart"):
                st.session_state.cart = []
                st.rerun()
        else:
            st.info("Cart is empty.")
    
    with col_right:
        st.subheader("Order Options")
        
        cust_options = ["Walk-in Customer"] + [f"{c['name']} (ID: {c['customer_id']})" for c in customers]
        cust_idx = st.selectbox("Select Customer", range(len(cust_options)), format_func=lambda x: cust_options[x])
        
        selected_cust_id = None
        use_prepaid = False
        
        if cust_idx > 0:
            selected_cust = customers[cust_idx - 1]
            selected_cust_id = selected_cust["customer_id"]
            st.caption(f"Available Prepaid Balance: ₱{selected_cust.get('prepaid_credits', 0.0):.2f}")
            use_prepaid = st.checkbox("Pay using Prepaid Balance")
        
        order_type = st.radio("Order Type", ["walk_in", "delivery"],
                              format_func=lambda x: "Walk-in" if x == "walk_in" else "Home Delivery")
        
        total_price = sum(item["subtotal"] for item in st.session_state.cart)
        st.markdown(f"### Total: **₱{total_price:.2f}**")
        
        if st.button("✅ Checkout Order", type="primary", use_container_width=True, disabled=not st.session_state.cart):
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
    
    tab1, tab2, tab3 = st.tabs(["📋 Current Stock", "✏️ Edit Product & Stock", "➕ Add New Product"])
    
    with tab1:
        products = inventory_service.get_all_products(owner_id)
        if products:
            st.dataframe(
                pd.DataFrame(products)[["product_id", "name", "category", "unit_price", "quantity", "empty_quantity"]],
                use_container_width=True)
        else:
            st.info("No items in inventory.")
    
    with tab2:
        st.subheader("Modify Product Details or Stock")
        products = inventory_service.get_all_products(owner_id)
        if products:
            prod_map = {f"{p['name']} (ID: {p['product_id']})": p for p in products}
            selected_label = st.selectbox("Select Item to Update", list(prod_map.keys()))
            prod = prod_map[selected_label]
            
            with st.form("edit_product_form"):
                edit_name = st.text_input("Product Name", value=prod["name"])
                
                cats = ["Refill", "Container/Jug", "Dispenser/Accessory", "Service"]
                curr_idx = cats.index(prod.get("category")) if prod.get("category") in cats else 0
                edit_cat = st.selectbox("Category", cats, index=curr_idx)
                
                col1, col2, col3 = st.columns(3)
                edit_price = col1.number_input("Unit Price (₱)", min_value=0.0, step=1.0,
                                               value=float(prod["unit_price"]))
                edit_stock = col2.number_input("Filled Stock Quantity", min_value=0, step=1,
                                               value=int(prod["quantity"]))
                edit_empty = col3.number_input("Empty Jugs Available", min_value=0, step=1,
                                               value=int(prod.get("empty_quantity", 0)))
                
                if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                    inventory_service.update_product(
                        product_id=prod["product_id"],
                        user_id=owner_id,
                        name=edit_name.strip(),
                        category=edit_cat,
                        price=edit_price,
                        quantity=edit_stock,
                        empty_quantity=edit_empty
                    )
                    st.success(f"Updated **{edit_name}** successfully!")
                    st.rerun()
        else:
            st.info("No products available to edit.")
    
    with tab3:
        st.subheader("Register New Product / Item")
        with st.form("add_product_form", clear_on_submit=True):
            p_name = st.text_input("Product Name *", placeholder="e.g., 5-Gallon Slim Refill")
            p_category = st.selectbox("Category", ["Refill", "Container/Jug", "Dispenser/Accessory", "Service"])
            
            col1, col2, col3 = st.columns(3)
            p_price = col1.number_input("Unit Price (₱) *", min_value=0.0, step=1.0, value=35.0)
            p_stock = col2.number_input("Initial Filled Stock *", min_value=0, step=1, value=50)
            p_empty = col3.number_input("Initial Empty Jugs", min_value=0, step=1, value=20)
            
            if st.form_submit_button("➕ Register Product", type="primary", use_container_width=True):
                if not p_name.strip():
                    st.warning("Please provide a product name.")
                else:
                    inventory_service.create_product(
                        user_id=owner_id,
                        name=p_name.strip(),
                        category=p_category,
                        price=p_price,
                        quantity=p_stock,
                        empty_quantity=p_empty
                    )
                    st.success(f"Added **{p_name}** to inventory!")
                    st.rerun()


def render_customers_page(user: dict):
    st.header("👥 Customer Management")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    with st.form("add_customer_form", clear_on_submit=True):
        st.subheader("Add Customer Profile")
        c_name = st.text_input("Customer Name *")
        c_phone = st.text_input("Phone Number")
        c_address = st.text_area("Delivery Address")
        if st.form_submit_button("Save Customer"):
            if c_name:
                inventory_service.create_customer(owner_id, c_name, c_phone, c_address)
                st.success("Customer added successfully!")
                st.rerun()
            else:
                st.warning("Customer name is required.")
    
    st.divider()
    customers = inventory_service.get_all_customers(owner_id)
    if customers:
        st.dataframe(pd.DataFrame(customers), use_container_width=True)


def render_deliveries_page(user: dict):
    st.header("🚚 Delivery Tracking & Log")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    deliveries = inventory_service.get_pending_deliveries(owner_id)
    if deliveries:
        for d in deliveries:
            created_at = d.get("created_at", "N/A")
            with st.expander(f"Delivery #{d['delivery_id']} — {d.get('customer_name', 'Walk-in')} ({created_at})"):
                st.write(f"**Address:** {d.get('address', 'N/A')}")
                st.write(f"**Phone:** {d.get('phone', 'N/A')}")
                st.write(f"**Order Placed:** `{created_at}`")
                
                empty_ret = st.number_input(f"Empty Jugs Collected", min_value=0, value=0,
                                            key=f"empty_in_{d['delivery_id']}")
                if st.button(f"Mark Delivered #{d['delivery_id']}", key=f"btn_deliv_{d['delivery_id']}"):
                    inventory_service.complete_delivery(d["delivery_id"], empty_returned=empty_ret)
                    st.success("Delivery marked as completed!")
                    st.rerun()
    else:
        st.info("No active pending deliveries.")


def render_ai_marketing_page(user: dict):
    st.header("🤖 AI Marketing & Tech Hub")
    st.caption("Automated promo generation and customer engagement.")
    
    tab1, tab2 = st.tabs(["📢 Promo Campaign Generator", "🎯 Smart Re-engagement"])
    
    with tab1:
        st.subheader("Generate SMS & Social Media Promos")
        promo_type = st.selectbox("Campaign Objective",
                                  ["Refill Discount", "New Customer Welcome", "Prepaid Jug Promo"])
        audience = st.text_input("Target Audience", value="Residential Neighborhoods")
        discount = st.slider("Discount Offer (%)", 0, 50, 10)
        
        if st.button("✨ Generate Promo Copy", type="primary"):
            st.divider()
            st.code(
                f"💧 Stay hydrated with {user.get('station_name', 'Water Station')}!\n\n"
                f"Special Offer for {audience}: Get {discount}% OFF on your next refill! "
                f"Clean & fast doorstep delivery. Text/call us today to place your order! 🚛💦",
                language="markdown"
            )
    
    with tab2:
        st.subheader("💡 Business Recommendations")
        st.info("• **Retention Alert:** 12 customers have not ordered refills in over 14 days.")
        st.success("• **Peak Delivery Window:** Highest delivery demand occurs between 10 AM - 1 PM on Saturdays.")


def render_settings_page(user: dict):
    st.header("⚙️ Station Settings & Workforce Management")
    owner_id = user["user_id"] if user["role"] == "owner" else user.get("owner_id", user["user_id"])
    
    if user["role"] == "owner":
        st.subheader("Pending Workforce Applications")
        pending_reqs = db.get_pending_requests_for_owner(owner_id) if hasattr(db,
                                                                              "get_pending_requests_for_owner") else []
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
            st.info("No pending join applications.")
        
        st.divider()
        st.subheader("Active Team Members")
        team = db.get_workforce(owner_id) if hasattr(db, "get_workforce") else []
        if team:
            st.dataframe(pd.DataFrame(team)[["username", "email", "role", "is_active"]], use_container_width=True)
    else:
        st.info("Workforce settings can only be managed by the station owner.")

def show_dashboard():
    user = st.session_state.user
    
    st.sidebar.title(f"💧 {user.get('station_name', 'Water Station')}")
    st.sidebar.caption(f"Logged in as **{user['username']}** ({user['role'].upper()})")
    
    menu_options = [
        "📊 Dashboard Overview",
        "📈 Sales Reports",
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
    
    if selected_tab == "📊 Dashboard Overview":
        render_dashboard_overview(user)
    elif selected_tab == "📈 Sales Reports":
        render_sales_reports_section(user)
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