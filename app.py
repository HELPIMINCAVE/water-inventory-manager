import os
from typing import Any, Optional
import resend
import streamlit as st
from database import Database
from inventory_service import InventoryService
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
                if user and get_str(user, "email").lower() == clean_email.lower():
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
                and st.session_state.otp_store[clean_user] == input_code.strip()
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

    if menu == "⚙️ Security & Account Settings":
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

            new_pass = st.text_input(
                "New Password", type="password", key="reset_new_pass"
            )
            confirm_pass = st.text_input(
                "Confirm New Password", type="password", key="reset_conf_pass"
            )

            if st.button("Request Confirmation OTP"):
                clean_new = new_pass.strip()
                clean_conf = confirm_pass.strip()

                if not clean_new:
                    st.error("New password cannot be blank.")
                elif clean_new != clean_conf:
                    st.error("Passwords do not match.")
                elif username.lower() == clean_new.lower():
                    st.error("Password cannot be the same as your username.")
                else:
                    is_valid, msg = validate_strict_password(
                        clean_new, username=username
                    )
                    if not is_valid:
                        st.error(msg)
                    else:
                        otp_code = generate_otp()
                        st.session_state.otp_store[f"reset_{username}"] = {
                            "code": otp_code,
                            "new_password": clean_new,
                        }
                        if send_email_notification(
                            user_email,
                            "Confirm Password Reset OTP",
                            f"Your password reset OTP is: <strong>{otp_code}</strong>",
                        ):
                            st.success("Confirmation OTP sent to your email!")

            confirm_otp = st.text_input("Enter Confirmation OTP", key="conf_reset_otp")
            if st.button(
                "Confirm & Update Password",
                type="primary",
                use_container_width=True,
            ):
                reset_data = st.session_state.otp_store.get(f"reset_{username}")
                if reset_data and reset_data["code"] == confirm_otp.strip():
                    success = db.update_user_password(
                        user_id, reset_data["new_password"]
                    )
                    if success:
                        st.success(
                            "Password updated successfully! Please log in using"
                            " your new credentials."
                        )
                        st.session_state.otp_logged_in = False
                        del st.session_state.otp_store[f"reset_{username}"]
                    else:
                        st.error("Database update failed.")
                else:
                    st.error("Invalid confirmation OTP.")

        with tab_deactivate:
            st.subheader("Deactivate Account")
            st.warning(
                "Deactivating your account disables future access for this"
                " user."
            )

            deact_pass = st.text_input(
                "Current Password", type="password", key="deact_pass"
            )

            if st.button("Request Deactivation OTP"):
                if not deact_pass.strip():
                    st.error("Password cannot be blank.")
                else:
                    user_check = db.verify_user(username, deact_pass.strip())
                    if user_check:
                        deact_otp = generate_otp()
                        st.session_state.otp_store[f"deact_{username}"] = deact_otp
                        if send_email_notification(
                            user_email,
                            "Deactivate Account OTP",
                            f"Your deactivation OTP is: <strong>{deact_otp}</strong>",
                        ):
                            st.success("Deactivation OTP sent to your email!")
                    else:
                        st.error("Incorrect password.")

            input_deact_otp = st.text_input("Enter Deactivation OTP", key="deact_otp_input")
            if st.button(
                "Confirm Account Deactivation",
                type="primary",
                use_container_width=True,
            ):
                stored_deact_otp = st.session_state.otp_store.get(
                    f"deact_{username}"
                )
                if (
                    stored_deact_otp
                    and stored_deact_otp == input_deact_otp.strip()
                ):
                    db.deactivate_user_account(user_id)
                    st.success("Account deactivated.")
                    st.session_state.authenticated = False
                    st.session_state.user = None
                    st.rerun()
                else:
                    st.error("Invalid deactivation OTP.")

    elif menu == "🛒 Point of Sale":
        st.header("🛒 Point of Sale & Checkout")
        st.info("POS dashboard functional.")

    elif menu == "📦 Products & Inventory":
        st.header("📦 Inventory Management")
        st.info("Inventory management dashboard functional.")

    elif menu == "👥 Customer Retention":
        st.header("👥 Customer Retention")
        st.info("Customer management dashboard functional.")

    elif menu == "🚚 Delivery Dispatch":
        st.header("🚚 Delivery Management")
        st.info("Logistics dashboard functional.")


if __name__ == "__main__":
    if st.session_state.authenticated and st.session_state.user:
        show_dashboard()
    else:
        show_auth_page()