import io
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from database import (
    init_db, create_user, authenticate_user, get_user_by_id,
    add_expense, get_expenses_df, delete_expense, update_expense,
    set_budget, get_budget, get_month_total, get_top_category
)

st.set_page_config(page_title="Multi-user Expense Tracker", page_icon="💳", layout="wide")

# ----- Helpers -----
DEFAULT_CATEGORIES = [
    "Food", "Travel", "Shopping", "Bills", "Entertainment", "Health",
    "Groceries", "Education", "Rent", "Utilities", "Other"
]

def month_str(d: date) -> str:
    return d.strftime("%Y-%m")

def to_date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def ensure_login_state():
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = None
    if "username" not in st.session_state:
        st.session_state["username"] = None

# Initialize DB
init_db()
ensure_login_state()

# ----- Top-level layout -----
st.title("💳 Multi-user Expense Tracker")
st.markdown("Private accounts — each user sees only their own expenses. Built with Streamlit + SQLite.")

# --- Sidebar: Login / User panel ---
with st.sidebar:
    st.header("Account")
    if st.session_state["user_id"] is None:
        mode = st.radio("Choose action", ("Login", "Sign up"))
        if mode == "Login":
            with st.form("login_form"):
                uname = st.text_input("Username")
                pwd = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in")
                if submitted:
                    uid = authenticate_user(uname, pwd)
                    if uid:
                        st.session_state["user_id"] = uid
                        st.session_state["username"] = uname.strip()
                        st.success(f"Logged in as {st.session_state['username']}")
                        st.rerun()

                    else:
                        st.error("Invalid username or password.")
        else:
            with st.form("signup_form"):
                uname = st.text_input("Choose username")
                pwd = st.text_input("Choose password", type="password")
                pwd2 = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create account")
                if submitted:
                    if not uname or not pwd:
                        st.error("Please provide username and password.")
                    elif pwd != pwd2:
                        st.error("Passwords do not match.")
                    else:
                        new_id = create_user(uname.strip(), pwd)
                        if new_id:
                            st.success("Account created — you can now log in.")
                        else:
                            st.error("Username already exists or invalid input.")
    else:
        st.write(f"👤 **{st.session_state['username']}**")
        if st.button("Log out"):
            st.session_state["user_id"] = None
            st.session_state["username"] = None
            st.rerun()


    st.divider()
    st.header("Filters & Budget")
    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start date", date(today.year, today.month, 1))
    with col2:
        end = st.date_input("End date", today)
    selected_categories = st.multiselect("Categories", DEFAULT_CATEGORIES, default=DEFAULT_CATEGORIES)
    st.divider()
    st.subheader("Monthly Budget")
    budget_month = st.date_input("Budget month", date(today.year, today.month, 1))
    if st.session_state["user_id"]:
        budget_month_key = month_str(budget_month)
        current_budget = get_budget(st.session_state["user_id"], budget_month_key)
        st.caption(f"Current budget for {budget_month_key}: " + (f"₹{current_budget:,.2f}" if current_budget is not None else "not set"))
        new_budget = st.number_input("Set / Update budget (₹)", min_value=0.0, step=100.0, value=float(current_budget or 0.0))
        if st.button("Save Budget"):
            set_budget(st.session_state["user_id"], budget_month_key, float(new_budget))
            st.success(f"Budget for {budget_month_key} set to ₹{new_budget:,.2f}")
            st.rerun()

    else:
        st.info("Log in to set monthly budget.")

# ---- Main content ----
if st.session_state["user_id"] is None:
    st.info("Please log in or sign up from the sidebar to use your personal expense tracker.")
    st.stop()

# Load data for the logged-in user with filters
start_str = to_date_str(start)
end_str = to_date_str(end)
df = get_expenses_df(st.session_state["user_id"], start_str, end_str, selected_categories)
if not df.empty:
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    df["Month"] = df["Date"].dt.strftime("%Y-%m")

# Tabs
tab_add, tab_browse, tab_insights, tab_reports, tab_account = st.tabs(["➕ Add", "📋 Browse", "📈 Insights", "📥 Reports", "⚙️ Account"])

with tab_add:
    st.subheader("Add a new expense")
    with st.form("add_expense_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            expense_date = st.date_input("Date", date.today())
        with c2:
            category = st.selectbox("Category", DEFAULT_CATEGORIES + ["Custom..."])
            if category == "Custom...":
                category = st.text_input("Custom category", "").strip() or "Other"
        with c3:
            amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.2f")

        note = st.text_input("Note (optional)")

        submitted = st.form_submit_button("Add Expense")
        if submitted:
            if amount <= 0:
                st.error("Amount should be greater than 0.")
            else:
                new_id = add_expense(st.session_state["user_id"], to_date_str(expense_date), category, float(amount), note)
                st.success(f"Added expense #{new_id} — {category} ₹{amount:,.2f} on {expense_date}")

                # Budget alert
                mkey = month_str(expense_date)
                b = get_budget(st.session_state["user_id"], mkey)
                if b is not None:
                    total = get_month_total(st.session_state["user_id"], mkey)
                    ratio = total / b if b > 0 else 0
                    if ratio >= 1.0:
                        st.error(f"⚠️ Budget exceeded for {mkey}! Spent ₹{total:,.2f} / ₹{b:,.2f}.")
                    elif ratio >= 0.9:
                        st.warning(f"🔔 Nearing budget for {mkey}: Spent ₹{total:,.2f} / ₹{b:,.2f} ({ratio*100:.1f}%).")
                    else:
                        st.info(f"Budget status for {mkey}: ₹{total:,.2f} / ₹{b:,.2f} ({ratio*100:.1f}%).")

                st.rerun()


with tab_browse:
    st.subheader("Your expenses (filtered)")
    if df.empty:
        st.info("No expenses found for the current filters.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("#### Edit or Delete an expense")
        with st.expander("Quick edit / delete"):
            ids = df["ID"].tolist()
            if ids:
                selected_id = st.selectbox("Select ID to edit/delete", ids)
                row = df[df["ID"] == selected_id].iloc[0]
                ec1, ec2, ec3, ec4 = st.columns(4)
                with ec1:
                    e_date = st.date_input("Date", pd.to_datetime(row["Date"]).date())
                with ec2:
                    options = DEFAULT_CATEGORIES + ["Custom..."]
                    try:
                        default_index = options.index(row["Category"]) if row["Category"] in DEFAULT_CATEGORIES else options.index("Custom...")
                    except ValueError:
                        default_index = len(options) - 1
                    e_cat = st.selectbox("Category", options, index=default_index)
                    if e_cat == "Custom...":
                        e_cat = st.text_input("Custom category", row["Category"]).strip() or "Other"
                with ec3:
                    e_amount = st.number_input("Amount (₹)", min_value=0.0, value=float(row["Amount"]), step=10.0, format="%.2f")
                with ec4:
                    e_note = st.text_input("Note", row["Note"])

                colu1, colu2 = st.columns(2)
                with colu1:
                    if st.button("Save changes"):
                        update_expense(st.session_state["user_id"], int(selected_id), to_date_str(e_date), e_cat, float(e_amount), e_note)
                        st.success(f"Updated expense #{selected_id}")
                        st.rerun()

                with colu2:
                    if st.button("Delete"):
                        delete_expense(st.session_state["user_id"], int(selected_id))
                        st.warning(f"Deleted expense #{selected_id}")
                        st.rerun()

with tab_insights:
    st.subheader("Spending insights")
    if df.empty:
        st.info("No data to visualize. Add some expenses!")
    else:
        total_spent = float(df["Amount"].sum())
        days = (pd.to_datetime(end) - pd.to_datetime(start)).days + 1
        avg_daily = total_spent / max(days, 1)
        txns = len(df)

        k1, k2, k3 = st.columns(3)
        k1.metric("Total spent (₹)", f"{total_spent:,.2f}")
        k2.metric("Avg daily spend (₹)", f"{avg_daily:,.2f}")
        k3.metric("Transactions", f"{txns}")

        # Top spending category
        top = get_top_category(st.session_state["user_id"], start_str, end_str)
        if top:
            st.info(f"🏷️ Top spending category in this period: **{top[0]}** — ₹{float(top[1]):,.2f}")

        # Charts
        st.markdown("#### Category-wise breakdown")
        cats = df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        fig1, ax1 = plt.subplots()
        cats.plot.pie(autopct='%.1f%%', ax=ax1)
        ax1.set_ylabel('')
        ax1.set_title('Share by Category')
        st.pyplot(fig1, use_container_width=True)

        st.markdown("#### Daily trend")
        daily = df.groupby("Date")["Amount"].sum()
        fig2, ax2 = plt.subplots()
        daily.plot(ax=ax2, marker='o')
        ax2.set_title("Daily Expenses Trend")
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Amount (₹)")
        st.pyplot(fig2, use_container_width=True)

        st.markdown("#### Monthly totals")
        monthly = df.groupby("Month")["Amount"].sum()
        fig3, ax3 = plt.subplots()
        monthly.plot(kind="bar", ax=ax3)
        ax3.set_xlabel("Month (YYYY-MM)")
        ax3.set_ylabel("Amount (₹)")
        ax3.set_title("Monthly Totals")
        st.pyplot(fig3, use_container_width=True)

        # Budget status for the last month in the filtered data
        if not df.empty:
            end_month_key = df["Month"].iloc[-1]
            b = get_budget(st.session_state["user_id"], end_month_key)
            if b is not None:
                spent_m = float(df[df["Month"] == end_month_key]["Amount"].sum())
                ratio = spent_m / b if b > 0 else 0
                if ratio >= 1.0:
                    st.error(f"⚠️ Budget exceeded for {end_month_key}! Spent ₹{spent_m:,.2f} / ₹{b:,.2f}.")
                elif ratio >= 0.9:
                    st.warning(f"🔔 Nearing budget for {end_month_key}: Spent ₹{spent_m:,.2f} / ₹{b:,.2f} ({ratio*100:.1f}%).")
                else:
                    st.success(f"Budget status for {end_month_key}: ₹{spent_m:,.2f} / ₹{b:,.2f} ({ratio*100:.1f}%).")

with tab_reports:
    st.subheader("Export / Download")
    if df.empty:
        st.info("No data to export for the current filters.")
    else:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        fname = f"{st.session_state['username']}_expenses_{start_str}_to_{end_str}.csv"
        st.download_button("Download CSV (filtered)", data=csv_bytes, file_name=fname, mime="text/csv")
        st.caption("CSV includes current filters (date range + categories).")

with tab_account:
    st.subheader("Account")
    user = get_user_by_id(st.session_state["user_id"])
    if user:
        st.write(f"**Username:** {user[1]}")
        st.write(f"**Created at:** {user[2]}")
    st.markdown("**Important:** This demo stores hashed passwords locally in the app database. For production, use a hardened auth system.")

st.caption("Built with Streamlit, Pandas, Matplotlib, and SQLite. Each account stores data privately.")
