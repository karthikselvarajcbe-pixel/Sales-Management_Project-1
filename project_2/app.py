import streamlit as st
import pandas as pd
from decimal import Decimal
from db import get_connection

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Aviation Dashboard", layout="wide")

# ---------------- CUSTOM UI ----------------
st.markdown("""
<style>
.stApp {
    background-image: url("https://images.unsplash.com/photo-1529070538774-1843cb3265df");
    background-size: cover;
    background-attachment: fixed;
}
section[data-testid="stSidebar"] {
    background-color: #111 !important;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOGIN ----------------
def login_user(username, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM users
        WHERE username = %s AND password = %s
    """, (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

# ---------------- LOAD DATA ----------------
def load_data(user):
    conn = get_connection()
    user_role = str(user.get("role", "")).strip().lower()

    if user_role == "admin":
        query = "SELECT * FROM customer_sales WHERE branch_id = %s"
        df = pd.read_sql(query, conn, params=(user["branch_id"],))
    else:
        query = "SELECT * FROM customer_sales"
        df = pd.read_sql(query, conn)

    conn.close()
    return df

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# =====================================================
# 🔐 LOGIN
# =====================================================
if st.session_state.user is None:

    st.title("✈️ Aviation Academy")

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.user = user
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

# =====================================================
# 🏠 MAIN APP
# =====================================================
else:
    user = st.session_state.user
    user_role = str(user.get("role", "")).strip().lower()
    is_admin = user_role == "admin"
    is_super_admin = user_role in ("super admin", "superadmin", "super-admin")

    df = load_data(user)

    # ---------- SAFE COLUMNS ----------
    for col in ["gross_sales", "received_amount", "pending_amount"]:
        if col not in df.columns:
            df[col] = 0

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # =====================================================
    # 🧭 SIDEBAR GLOBAL FILTERS
    # =====================================================
    st.sidebar.markdown("## ✈️ Aviation Dashboard")
    st.sidebar.write(f"👤 {user['username']}")
    st.sidebar.write(f"🔑 {user['role']}")

    # ---- DATE FILTER ----
    if "date" in df.columns and not df["date"].isna().all():
        min_date = df["date"].min()
        max_date = df["date"].max()

        st.session_state.from_date = st.sidebar.date_input(
            "From Date", min_value=min_date, max_value=max_date, value=min_date
        )
        st.session_state.to_date = st.sidebar.date_input(
            "To Date", min_value=min_date, max_value=max_date, value=max_date
        )
    else:
        st.session_state.from_date = None
        st.session_state.to_date = None

    # ---- BRANCH FILTER ----
    if "branch_id" in df.columns:
        if is_super_admin:
            st.session_state.branch_filter = st.sidebar.selectbox(
                "Branch",
                ["All"] + list(df["branch_id"].dropna().unique())
            )
        elif is_admin:
            st.sidebar.markdown(f"**Branch:** {user['branch_id']}")
            st.session_state.branch_filter = user["branch_id"]
        else:
            st.session_state.branch_filter = st.sidebar.selectbox(
                "Branch",
                ["All"] + list(df["branch_id"].dropna().unique())
            )
    else:
        st.session_state.branch_filter = "All"

    # ---- PRODUCT FILTER ----
    if "product_name" in df.columns:
        st.session_state.product_filter = st.sidebar.selectbox(
            "Product",
            ["All"] + list(df["product_name"].dropna().unique())
        )
    else:
        st.session_state.product_filter = "All"

    if st.sidebar.button("🚪 Logout"):
        st.session_state.user = None
        st.rerun()

    # =====================================================
    # 🔥 GLOBAL FILTER FUNCTION (USED BY ALL TABS)
    # =====================================================
    def apply_global_filters(data):
        filtered = data.copy()

        # Date filter
        if st.session_state.from_date and st.session_state.to_date and "date" in filtered.columns:
            filtered = filtered[
                (filtered["date"] >= pd.to_datetime(st.session_state.from_date)) &
                (filtered["date"] <= pd.to_datetime(st.session_state.to_date))
            ]

        # Branch filter
        if st.session_state.branch_filter != "All" and "branch_id" in filtered.columns:
            filtered = filtered[filtered["branch_id"] == st.session_state.branch_filter]

        # Product filter
        if st.session_state.product_filter != "All" and "product_name" in filtered.columns:
            filtered = filtered[filtered["product_name"] == st.session_state.product_filter]

        return filtered

    # Apply ONCE globally
    filtered_df = apply_global_filters(df)

    # =====================================================
    # TABS
    # =====================================================
    tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Dashboard", "💳 Payments", "🙎🏻‍♂️ Add Customers", " 🎯 MYSQL Queries"
])

    # =====================================================
    # 📊 DASHBOARD
    # =====================================================
    with tab1:
        st.subheader("📊 Overview")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Sales", f"₹ {filtered_df['gross_sales'].sum():,.0f}")
        c2.metric("Received", f"₹ {filtered_df['received_amount'].sum():,.0f}")
        c3.metric("Pending", f"₹ {filtered_df['pending_amount'].sum():,.0f}")

        st.dataframe(filtered_df, use_container_width=True)

        

  
    # =====================================================
    # 💰 PAYMENTS
    # =====================================================
    with tab2:
        if "sale_id" in filtered_df.columns:

            selected_sale = st.selectbox("Sale ID", filtered_df["sale_id"])
            payment_amount = st.number_input("Amount", min_value=0.0)

            if st.button("Submit Payment"):
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT received_amount, pending_amount
                    FROM customer_sales
                    WHERE sale_id = %s
                """, (selected_sale,))

                result = cursor.fetchone()

                if not result:
                    st.error("Invalid sale")
                    conn.close()
                    st.stop()

                paid, pending = result
                payment = Decimal(str(payment_amount))

                if payment > Decimal(str(pending)):
                    st.error("Payment exceeds pending")
                    conn.close()
                    st.stop()

                new_paid = Decimal(str(paid)) + payment

                cursor.execute("""
                    UPDATE customer_sales
                    SET received_amount = %s
                    WHERE sale_id = %s
                """, (new_paid, selected_sale))

                conn.commit()
                conn.close()

                st.success("Payment updated")
                st.rerun()

    # =====================================================
    # 👤 ADD CUSTOMER
    # =====================================================
    

# ---------------- TAB 3 ----------------
with tab3:
    st.subheader("➕ Add Customer")

    # -------- Branch Selection --------
    if is_admin:
        branch_id = user["branch_id"]
        st.success(f"Branch ID: {branch_id}")
    else:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT branch_id FROM branches ORDER BY branch_id")
        branches = [row[0] for row in cursor.fetchall()]
        conn.close()

        if branches:
            branch_id = st.selectbox("Select Branch", branches)
        else:
            st.warning("No branches configured.")
            branch_id = None

    st.divider()

    # -------- Form Layout --------
    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input("Customer Name")

        product_options = ["Select Product", "DS", "BA", "DA", "FSD", "ML", "AI", "BI", "SQL"]
        product_name = st.selectbox("Product Name", product_options)

        gross_sales = st.number_input("Gross Sale", min_value=0.0)

    with col2:
        received_amount = st.number_input("Received Amount", min_value=0.0)
        mobile_number = st.text_input("Mobile Number")
        date = st.date_input("Date")

    # -------- Logic --------
    pending_amount = gross_sales - received_amount
    status = "Close" if pending_amount == 0 else "Open"

    st.divider()

    col3, col4 = st.columns(2)
    col3.metric("Pending Amount", f"₹{pending_amount}")
    col4.metric("Status", status)

    st.divider()

    # -------- Submit --------
    if st.button("✅ Add Customer", use_container_width=True):
        if branch_id is None:
            st.error("Select a branch before adding a customer.")
        elif product_name == "Select Product":
            st.error("Please select a valid product.")
        elif name == "":
            st.error("Customer name cannot be empty.")
        else:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO customer_sales
                (name, branch_id, product_name, gross_sales, received_amount, mobile_number, date, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                name, branch_id, product_name,
                gross_sales, received_amount,
                mobile_number, date, status
            ))
            conn.commit()
            conn.close()

            st.success("✅ Customer added successfully")
            st.rerun()

 # =====================================================
# 🎯 MYSQL QUERIES - TAB 4
# =====================================================

def run_query(query):
    try:
        conn = get_connection()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Database Error: {e}")
        return None


with tab4:

    st.title("📊 Reports (Query Explorer)")

    query_options = {
        "1. Retrieve all sales belonging to the Chennai branch":
        """
        SELECT cs.*
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id
        WHERE b.branch_name = 'Chennai';
        """,

        "2. Retrieve all records from the customer_sales table":
        "SELECT * FROM customer_sales;",

        "3. Retrieve all records from the branches table":
        "SELECT * FROM branches;",

        "4. Retrieve all records from the payment_splits table":
        "SELECT * FROM payment_splits;",

        "5. Calculate total gross sales across all branches":
        "SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales;",

        "6. Calculate total received amount across all sales":
        "SELECT SUM(received_amount) AS total_received FROM customer_sales;",

        "7. Calculate total pending amount across all sales":
        "SELECT SUM(pending_amount) AS total_pending FROM customer_sales;",

        "8. Count total number of sales per branch":
        """
        SELECT b.branch_name, COUNT(cs.sale_id) AS total_sales
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id
        GROUP BY b.branch_name;
        """,

        "9. Find the branch with highest total gross sales":
        """
        SELECT b.branch_name, SUM(cs.gross_sales) AS total_sales
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id
        GROUP BY b.branch_name
        ORDER BY total_sales DESC
        LIMIT 1;
        """,

        "10. Display sales along with payment method used":
        """
        SELECT cs.sale_id, cs.name, ps.payment_method, ps.amount
        FROM customer_sales cs
        JOIN payment_splits ps ON cs.sale_id = ps.sale_id;
        """,

        "11. Retrieve sales along with branch admin name":
        """
        SELECT cs.sale_id, cs.name, b.branch_name, b.admin_name
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id;
        """,

        "12. Retrieve sales details along with the branch name":
        """
        SELECT cs.*, b.branch_name
        FROM customer_sales cs
        JOIN branches b ON cs.branch_id = b.branch_id;
        """,

        "13. Retrieve sales details with total payment received":
        """
        SELECT cs.sale_id, cs.name, cs.gross_sales,
               COALESCE(SUM(ps.amount), 0) AS total_received
        FROM customer_sales cs
        LEFT JOIN payment_splits ps ON cs.sale_id = ps.sale_id
        GROUP BY cs.sale_id, cs.name, cs.gross_sales;
        """
    }

    selected_query = st.selectbox(
        "📌 Select a Query",
        list(query_options.keys())
    )

    if st.button("Run Query"):

        df_result = run_query(query_options[selected_query])

        if df_result is None:
            st.stop()

        if df_result.empty:
            st.warning("⚠️ No data found")
        elif df_result.shape == (1, 1):
            st.metric("Result", df_result.iloc[0, 0])
        else:
            st.dataframe(df_result, use_container_width=True)