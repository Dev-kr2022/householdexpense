"""Household Expense Tracker — Streamlit app with optional AI insights."""

import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency in local sqlite setups
    psycopg = None


def ensure_streamlit_run() -> None:
    if os.getenv("STREAMLIT_TEST_MODE") == "1":
        return
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return
    if __name__ == "__main__" and get_script_run_ctx() is None:
        raise RuntimeError("Please launch this app with `streamlit run app.py` instead of `python app.py`.")


ensure_streamlit_run()
st.set_page_config(page_title="Household Expenses", page_icon="🏠", layout="wide")

CATEGORIES = ["Grocery", "Food", "House Help", "Internet", "Electricity", "Gas", "Petrol", "Maintenance", "Cooper", "Cooper Doctor", "Car Servicing", "Car Wash", "Alcohol", "Parking", "Festival", "Misc", "Medical", "FTH"]
USERS = ["RN", "DK"]
DATABASE_PATH = Path(os.getenv("SQLITE_PATH", str(Path(__file__).with_name("expenses.db"))))
POSTGRES_TABLE_SQL = """CREATE TABLE IF NOT EXISTS expenses (
    id BIGSERIAL PRIMARY KEY,
    transaction_date TEXT NOT NULL,
    category TEXT NOT NULL,
    expense_user TEXT NOT NULL DEFAULT 'RN',
    amount REAL NOT NULL CHECK(amount > 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""
SQLITE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL,
    category TEXT NOT NULL,
    expense_user TEXT NOT NULL DEFAULT 'RN',
    amount REAL NOT NULL CHECK(amount > 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


def get_database_url() -> Optional[str]:
    if url := os.getenv("DATABASE_URL"):
        return url
    if url := os.getenv("SUPABASE_DATABASE_URL"):
        return url
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return None


def get_database_kind() -> str:
    return "postgres" if get_database_url() else "sqlite"


class PostgresConnectionAdapter:
    def __init__(self, connection):
        self.connection = connection
        self._cursor = None

    def execute(self, query, params=None):
        self._cursor = self.connection.cursor()
        translated_query = query.replace("?", "%s")
        self._cursor.execute(translated_query, params)
        return self._cursor

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def get_connection():
    if get_database_kind() == "postgres":
        if psycopg is None:
            raise RuntimeError("Install psycopg[binary] to use a Supabase/Postgres database.")
        try:
            connection = psycopg.connect(get_database_url(), sslmode="require")
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_TABLE_SQL)
            connection.commit()
            return PostgresConnectionAdapter(connection)
        except Exception as exc:
            st.warning(f"Supabase connection failed ({exc}); falling back to local SQLite database.")

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.execute(SQLITE_TABLE_SQL)
    connection.commit()
    return connection


def get_api_key() -> Optional[str]:
    """Read .env locally or Streamlit secrets after deployment."""
    if key := os.getenv("OPENAI_API_KEY"):
        return key
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def get_admin_password() -> Optional[str]:
    if password := os.getenv("ADMIN_PASSWORD"):
        return password
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return None


def authenticate_app() -> bool:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.login_error = ""

    if st.session_state.logged_in:
        return True

    admin_password = get_admin_password()
    if not admin_password:
        st.error("ADMIN_PASSWORD is not configured. Add it to .env or Streamlit secrets.")
        return False

    st.title("🔒 Household Expense Tracker — Login")
    st.write("Enter the admin password to open the app.")
    with st.form("login_form", clear_on_submit=True):
        login_password = st.text_input("Admin password", type="password", key="login_password")
        open_app = st.form_submit_button("Open app")
    if open_app:
        if login_password == admin_password:
            st.session_state.logged_in = True
            rerun_app()
            return False
        st.session_state.login_error = "Invalid admin password."

    if st.session_state.login_error:
        st.error(st.session_state.login_error)
    return False


def add_expense(transaction_date: date, category: str, user: str, amount: float, note: str) -> None:
    connection = get_connection()
    connection.execute(
        "INSERT INTO expenses (transaction_date, category, expense_user, amount, note) VALUES (?, ?, ?, ?, ?)",
        (transaction_date.isoformat(), category, user, amount, note.strip()),
    )
    connection.commit()


def update_expense(expense_id: int, transaction_date: date, category: str, user: str, amount: float, note: str) -> None:
    connection = get_connection()
    connection.execute(
        "UPDATE expenses SET transaction_date = ?, category = ?, expense_user = ?, amount = ?, note = ? WHERE id = ?",
        (transaction_date.isoformat(), category, user, amount, note.strip(), expense_id),
    )
    connection.commit()


def delete_expense(expense_id: int) -> None:
    connection = get_connection()
    connection.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    connection.commit()


def flush_expenses(start_date: date, end_date: date) -> int:
    connection = get_connection()
    cursor = connection.execute(
        "DELETE FROM expenses WHERE transaction_date BETWEEN ? AND ?",
        (start_date.isoformat(), end_date.isoformat()),
    )
    connection.commit()
    return cursor.rowcount


def build_expense_query(categories: list[str], users: list[str], is_postgres: bool = False) -> tuple[str, list[str]]:
    placeholder = "%s" if is_postgres else "?"
    category_placeholders = ", ".join(placeholder for _ in categories)
    user_placeholders = ", ".join(placeholder for _ in users)
    query = f"""SELECT id, transaction_date AS Date, category AS Category, expense_user AS User, amount AS Amount, note AS Note
        FROM expenses WHERE transaction_date BETWEEN {placeholder} AND {placeholder} AND category IN ({category_placeholders}) AND expense_user IN ({user_placeholders})
        ORDER BY transaction_date DESC, id DESC"""
    params = [*categories, *users]
    return query, params


def load_expenses(start_date: date, end_date: date, categories: list[str], users: list[str]) -> pd.DataFrame:
    is_postgres = get_database_kind() == "postgres"
    query, params = build_expense_query(categories, users, is_postgres=is_postgres)
    query_params = [start_date.isoformat(), end_date.isoformat(), *params]
    rows = get_connection().execute(query, query_params).fetchall()
    return pd.DataFrame(rows, columns=["ID", "Date", "Category", "User", "Amount", "Note"])


def load_latest_expenses(limit: int = 100) -> pd.DataFrame:
    query = """SELECT id, transaction_date AS Date, category AS Category, expense_user AS User, amount AS Amount, note AS Note
        FROM expenses ORDER BY transaction_date DESC, id DESC LIMIT ?"""
    rows = get_connection().execute(query, (limit,)).fetchall()
    return pd.DataFrame(rows, columns=["ID", "Date", "Category", "User", "Amount", "Note"])


def get_default_report_start() -> date:
    connection = get_connection()
    row = connection.execute("SELECT MIN(transaction_date) FROM expenses").fetchone()
    if row and row[0]:
        try:
            return date.fromisoformat(row[0])
        except ValueError:
            pass
    today = date.today()
    return today.replace(day=1)


def get_default_report_end() -> date:
    connection = get_connection()
    row = connection.execute("SELECT MAX(transaction_date) FROM expenses").fetchone()
    if row and row[0]:
        try:
            return date.fromisoformat(row[0])
        except ValueError:
            pass
    return date.today()


def build_monthly_category_report(expenses: pd.DataFrame) -> pd.DataFrame:
    if expenses.empty:
        return pd.DataFrame(columns=["Month", "Category", "Amount"])

    monthly_expenses = expenses.copy()
    monthly_expenses["Month"] = pd.to_datetime(monthly_expenses["Date"]).dt.to_period("M").astype(str)
    monthly_expenses = monthly_expenses.groupby(["Month", "Category"], as_index=False)["Amount"].sum()
    return monthly_expenses.sort_values(["Month", "Category"]).reset_index(drop=True)


def build_monthly_average_summary(expenses: pd.DataFrame) -> pd.DataFrame:
    if expenses.empty:
        return pd.DataFrame(columns=["Month", "Total Expense", "Transaction Count"])

    monthly_expenses = expenses.copy()
    monthly_expenses["Month"] = pd.to_datetime(monthly_expenses["Date"]).dt.to_period("M").astype(str)
    summary = monthly_expenses.groupby("Month", as_index=False)["Amount"].sum().rename(columns={"Amount": "Total Expense"})
    summary["Total Expense"] = summary["Total Expense"].round(2)
    summary["Transaction Count"] = monthly_expenses.groupby("Month").size().values
    return summary.sort_values("Month").reset_index(drop=True)


def monthly_category_range_months(start_date: date, end_date: date) -> int:
    """Return the number of calendar months represented by an inclusive range."""
    if start_date > end_date:
        return 0
    return (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1


def database_context(expenses: pd.DataFrame) -> str:
    """Build AI context from every transaction stored in the database."""
    category_totals = expenses.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
    user_totals = expenses.groupby("User", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
    daily_totals = expenses.groupby("Date", as_index=False)["Amount"].sum().sort_values("Date")
    return f"""Database scope: all stored transactions
Transaction count: {len(expenses)}
Total spend: {expenses['Amount'].sum():.2f}
Category totals:\n{category_totals.to_csv(index=False)}
User totals:\n{user_totals.to_csv(index=False)}
Daily totals:\n{daily_totals.to_csv(index=False)}
All transactions:\n{expenses.to_csv(index=False)}"""


def ask_agent(api_key: str, question: str, context: str) -> str:
    response = OpenAI(api_key=api_key).chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a household-expense analysis assistant. Use only the supplied all-database transaction data to answer. If data cannot answer a question, say so. Be concise, use currency-neutral amounts, avoid financial, medical, or tax advice, and end with exactly three useful follow-up questions."},
            {"role": "user", "content": f"DATABASE DATA:\n{context}\n\nQUESTION:\n{question}"},
        ],
    )
    return response.choices[0].message.content or "No response received."


def rerun_app() -> None:
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
        return
    try:
        from streamlit.runtime.scriptrunner import RerunException
        from streamlit.runtime.scriptrunner_utils.script_requests import RerunData
    except ImportError:
        raise RuntimeError("Unable to rerun Streamlit app. Please refresh the browser.")
    raise RerunException(RerunData())


def main() -> None:
    load_dotenv()
    get_connection()
    if not authenticate_app():
        return
    st.title("🏠 Household Expense Tracker")
    st.caption("Record daily spending, view month-based reports, and ask the AI about all stored transactions.")

    with st.sidebar:
        st.header("Add an expense")
        with st.form("expense_form", clear_on_submit=True):
            transaction_date = st.date_input("Transaction date", value=date.today())
            category = st.selectbox("Category", CATEGORIES)
            user = st.selectbox("User", USERS)
            amount = st.number_input("Amount", min_value=0.01, step=1.0, format="%.2f")
            note = st.text_input("Note (optional)", placeholder="e.g. weekly vegetables")
            submitted = st.form_submit_button("Save expense", use_container_width=True)
        if submitted:
            add_expense(transaction_date, category, user, amount, note)
            st.success("Expense saved. Click '🔄 Refresh report' below to update views.")

        st.divider()
        st.header("Report filters")
        default_report_start = get_default_report_start()
        default_report_end = get_default_report_end()
        if st.button("Reset filters to saved transaction range"):
            st.session_state.report_start = default_report_start
            st.session_state.report_end = default_report_end
            st.session_state.selected_categories = CATEGORIES
            st.session_state.selected_users = USERS
            st.experimental_rerun()
        report_start = st.date_input("From", value=default_report_start, key="report_start")
        report_end = st.date_input("To", value=default_report_end, key="report_end")
        selected_categories = st.multiselect("Categories", CATEGORIES, default=CATEGORIES, key="selected_categories")
        selected_users = st.multiselect("Users", USERS, default=USERS, key="selected_users")
        report_name = st.text_input("Report name", value="Household expense report", key="report_name")
        
        st.divider()
        if st.button("🔄 Refresh report", type="primary", use_container_width=True):
            rerun_app()

    if report_start > report_end:
        st.error("The report start date must be on or before the end date.")
        return
    if not selected_categories:
        st.warning("Choose at least one category to generate a report.")
        return
    if not selected_users:
        st.warning("Choose at least one user to generate a report.")
        return

    expenses = load_expenses(report_start, report_end, selected_categories, selected_users)
    st.subheader(report_name)
    st.caption(f"{report_start:%d %b %Y} – {report_end:%d %b %Y} · {', '.join(selected_categories)}")

    month_start = report_start.replace(day=1)
    month_end = report_end.replace(day=1)
    available_months = list(pd.date_range(month_start, month_end, freq="MS"))
    current_month = date.today().replace(day=1)
    default_month = min(max(current_month, month_start), month_end)
    if "selected_month" not in st.session_state:
        st.session_state.selected_month = default_month
    selected_month = st.selectbox(
        "Select month for report and transactions",
        options=available_months,
        format_func=lambda value: value.strftime("%b %Y"),
        key="selected_month",
    )
    selected_month_str = selected_month.strftime("%Y-%m")
    monthly_expenses = expenses[expenses["Date"].str.startswith(selected_month_str, na=False)] if not expenses.empty else pd.DataFrame()
    total = monthly_expenses["Amount"].sum() if not monthly_expenses.empty else 0.0
    average = monthly_expenses["Amount"].mean() if not monthly_expenses.empty else 0.0
    highest = monthly_expenses.loc[monthly_expenses["Amount"].idxmax(), "Category"] if not monthly_expenses.empty else "—"
    col_one, col_two, col_three = st.columns(3)
    col_one.metric("Total spent", f"{total:,.2f}")
    col_two.metric("Transactions", len(monthly_expenses))
    col_three.metric("Largest category", highest)

    all_expenses = load_expenses(
        get_default_report_start(),
        get_default_report_end(),
        CATEGORIES,
        USERS,
    )

    report_tab, transactions_tab = st.tabs(["Report", "Transactions"])
    with report_tab:
        if monthly_expenses.empty:
            st.info(f"No expenses match the filters for {selected_month.strftime('%b %Y')}.")
        else:
            category_totals = monthly_expenses.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
            st.bar_chart(category_totals, x="Category", y="Amount")
            st.dataframe(category_totals, hide_index=True, use_container_width=True)
            st.markdown(f"### Total amount paid by user in {selected_month.strftime('%b %Y')}")
            if monthly_expenses.empty:
                st.info("No expenses found for the selected month.")
            else:
                monthly_user_totals = monthly_expenses.groupby("User", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
                st.dataframe(monthly_user_totals, hide_index=True, use_container_width=True)
            st.download_button("Download this report as CSV", data=monthly_expenses.to_csv(index=False).encode("utf-8"), file_name=f"household_expenses_{selected_month_str}.csv", mime="text/csv")
            st.caption(f"Average transaction amount: {average:,.2f}")

            split_pct = st.number_input("RN percent share of total", min_value=0, max_value=100, value=40, step=1, format="%d")
            monthly_total = monthly_expenses["Amount"].sum() if not monthly_expenses.empty else 0.0
            rn_share = monthly_total * split_pct / 100
            dk_share = monthly_total - rn_share
            split_data = pd.DataFrame(
                [{"User": "RN", "Percent": f"{split_pct}%", "Amount": rn_share}, {"User": "DK", "Percent": f"{100 - split_pct}%", "Amount": dk_share}]
            )
            st.markdown(f"### Split Summary of Total Expenses ({selected_month.strftime('%b %Y')})")
            st.dataframe(split_data, hide_index=True, use_container_width=True)
            col_a, col_b = st.columns(2)
            col_a.metric("RN share", f"{rn_share:,.2f}")
            col_b.metric("DK share", f"{dk_share:,.2f}")
            st.caption("The selected percentage is applied to the selected month’s total to split expenses between RN and DK.")

            monthly_user_totals = monthly_expenses.groupby("User", as_index=False)["Amount"].sum() if not monthly_expenses.empty else pd.DataFrame(columns=["User", "Amount"])
            actual_rn = float(monthly_user_totals.loc[monthly_user_totals["User"] == "RN", "Amount"].sum()) if not monthly_user_totals.empty else 0.0
            actual_dk = float(monthly_user_totals.loc[monthly_user_totals["User"] == "DK", "Amount"].sum()) if not monthly_user_totals.empty else 0.0
            rn_diff = actual_rn - rn_share
            dk_diff = actual_dk - dk_share
            if abs(rn_diff) < 0.005:
                settlement = "RN is settled with the target allocation."
            elif rn_diff > 0:
                settlement = f"RN paid Rs {rn_diff:,.2f} more than their target. DK should pay RN **Rs {rn_diff:,.2f}**."
            else:
                settlement = f"RN paid Rs {abs(rn_diff):,.2f} less than their target. DK should pay RN **Rs {abs(rn_diff):,.2f}**."

            st.markdown("### Settlement summary")
            st.write(f"Actual RN expense: {actual_rn:,.2f}")
            st.write(f"Actual DK expense: {actual_dk:,.2f}")
            st.markdown(settlement)

            st.markdown("### Monthly expense by category")
            default_monthly_category_end = report_end
            default_monthly_category_start = (pd.Timestamp(report_end).to_period("M") - 11).start_time.date()
            monthly_category_col_one, monthly_category_col_two = st.columns(2)
            monthly_category_start = monthly_category_col_one.date_input(
                "Monthly category range — from",
                value=default_monthly_category_start,
                key="monthly_category_start",
            )
            monthly_category_end = monthly_category_col_two.date_input(
                "Monthly category range — to",
                value=default_monthly_category_end,
                key="monthly_category_end",
            )
            month_count = monthly_category_range_months(monthly_category_start, monthly_category_end)
            if monthly_category_start > monthly_category_end:
                st.error("The monthly category range start date must be on or before the end date.")
            elif month_count > 12:
                st.error("Monthly expense by category can show a maximum of 12 calendar months. Choose a shorter range.")
            else:
                monthly_category_expenses = load_expenses(
                    monthly_category_start,
                    monthly_category_end,
                    selected_categories,
                    selected_users,
                )
                monthly_category_report = build_monthly_category_report(monthly_category_expenses)
                if monthly_category_report.empty:
                    st.info("No monthly breakdown is available for the selected range.")
                else:
                    monthly_category_pivot = monthly_category_report.pivot(index="Month", columns="Category", values="Amount").fillna(0)
                    monthly_category_pivot["Total"] = monthly_category_pivot.sum(axis=1)
                    monthly_category_pivot = monthly_category_pivot.sort_index()
                    monthly_category_pivot.index = monthly_category_pivot.index.map(lambda value: pd.to_datetime(value).strftime("%b-%y"))
                    transposed_grid = monthly_category_pivot.T
                    transposed_grid["Total"] = transposed_grid.sum(axis=1)
                    transposed_grid = transposed_grid.sort_index()
                    st.dataframe(transposed_grid, hide_index=False, use_container_width=True)

            st.markdown("### Average expense per month")
            range_avg_expenses = load_expenses(
                monthly_category_start,
                monthly_category_end,
                selected_categories,
                selected_users,
            )
            monthly_summary = build_monthly_average_summary(range_avg_expenses)
            if monthly_summary.empty:
                st.info("No monthly average data is available for the selected period.")
            else:
                mean_monthly_expense = monthly_summary["Total Expense"].mean()
                st.metric("Mean monthly expense", f"{mean_monthly_expense:,.2f}")
                chart_df = monthly_summary.set_index("Month")[["Total Expense"]].copy()
                chart_df["Mean Line"] = mean_monthly_expense
                st.line_chart(chart_df)
                st.dataframe(monthly_summary, hide_index=True, use_container_width=True)

    with transactions_tab:
        st.caption(f"Transactions for {selected_month.strftime('%b %Y')}")
        st.dataframe(monthly_expenses.drop(columns="ID"), hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Edit or delete a selected record")
        if monthly_expenses.empty:
            st.info(f"No records match the filters for {selected_month.strftime('%b %Y')}.")
        else:
            record_ids = monthly_expenses["ID"].tolist()
            selected_id = st.selectbox(
                "Choose a record to edit or delete",
                record_ids,
                format_func=lambda record_id: f"ID {record_id} — {monthly_expenses.loc[monthly_expenses['ID'] == record_id, 'Date'].iloc[0]} / {monthly_expenses.loc[monthly_expenses['ID'] == record_id, 'Category'].iloc[0]} / {monthly_expenses.loc[monthly_expenses['ID'] == record_id, 'Amount'].iloc[0]:.2f}",
            )
            selected = monthly_expenses.loc[monthly_expenses["ID"] == selected_id].iloc[0]
            st.caption("Selected record")
            st.dataframe(
                selected[["Date", "Category", "User", "Amount", "Note"]].to_frame().T,
                hide_index=True,
                use_container_width=True,
            )

            with st.form("edit_record_form", clear_on_submit=False):
                edit_date = st.date_input("Transaction date", value=pd.to_datetime(selected["Date"]).date(), key=f"edit_date_{selected_id}")
                edit_category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(selected["Category"]), key=f"edit_category_{selected_id}")
                edit_user = st.selectbox("User", USERS, index=USERS.index(selected["User"]), key=f"edit_user_{selected_id}")
                edit_amount = st.number_input("Amount", min_value=0.01, step=1.0, value=float(selected["Amount"]), format="%.2f", key=f"edit_amount_{selected_id}")
                edit_note = st.text_input("Note", value=str(selected["Note"]), key=f"edit_note_{selected_id}")
                update_record = st.form_submit_button("Update record")
            if update_record:
                update_expense(selected_id, edit_date, edit_category, edit_user, edit_amount, edit_note)
                st.success("Record updated.")
                rerun_app()

            with st.form("delete_record_form", clear_on_submit=False):
                delete_password = st.text_input("Admin password", type="password", key=f"delete_password_{selected_id}")
                delete_record = st.form_submit_button("Delete record")
            if delete_record:
                if delete_password != get_admin_password():
                    st.error("Admin password is incorrect. Record was not deleted.")
                else:
                    delete_expense(selected_id)
                    st.success("Record deleted.")
                    rerun_app()

        st.divider()
        st.subheader("Flush records by date")
        flush_start = st.date_input("Flush from", value=report_start, key="flush_start")
        flush_end = st.date_input("Flush to", value=report_end, key="flush_end")
        if st.button("Delete records in date range"):
            if flush_start > flush_end:
                st.error("The start date must be on or before the end date.")
            else:
                deleted = flush_expenses(flush_start, flush_end)
                if deleted:
                    st.success(f"Deleted {deleted} record(s) from {flush_start:%Y-%m-%d} to {flush_end:%Y-%m-%d}.")
                else:
                    st.info("No records found in that range.")
                rerun_app()

    st.divider()
    st.header("AI expense agent")
    st.write("Ask about any transaction in the database. The selected report month does not limit these answers.")
    common_questions = [
        "Which categories cost the most across all transactions?",
        "How did spending change over the full database history?",
        "What are the largest individual expenses?",
        "Which dates had unusually high spending?",
        "How much did each user spend in total?",
    ]
    question_choice = st.selectbox("Common questions", ["Write my own question"] + common_questions)
    custom_question = st.text_area("Your question", placeholder="e.g. How much did I spend on grocery and petrol?")
    question = custom_question.strip() or (question_choice if question_choice != "Write my own question" else "")
    if st.button("Ask AI agent", type="primary", disabled=all_expenses.empty):
        if not question:
            st.warning("Choose a common question or write one of your own.")
        elif not (api_key := get_api_key()):
            st.error("OPENAI_API_KEY is missing. Add it to .env or Streamlit secrets first.")
        else:
            with st.spinner("Reading all database transactions…"):
                try:
                    answer = ask_agent(api_key, question, database_context(all_expenses))
                except Exception:
                    st.error("The AI agent could not respond. Check the API key and network connection.")
                else:
                    st.markdown(answer)


if __name__ == "__main__":
    main()
