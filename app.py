"""Household Expense Tracker — Streamlit app with optional AI insights."""

import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


def ensure_streamlit_run() -> None:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return
    if get_script_run_ctx() is None:
        raise RuntimeError("Please launch this app with `streamlit run app.py` instead of `python app.py`.")


ensure_streamlit_run()
st.set_page_config(page_title="Household Expenses", page_icon="🏠", layout="wide")

CATEGORIES = ["Grocery", "Internet", "Electricity", "Gas", "Petrol", "Maintenance", "Cooper", "Cooper Doctor", "Car Servicing", "Car Wash", "Alcohol", "Parking", "Festival", "Misc", "Medical", "FTH"]
USERS = ["RN", "DK"]
ADMIN_PASSWORD = "2498"
DATABASE_PATH = Path(__file__).with_name("expenses.db")


def get_database_url() -> Optional[str]:
    return os.getenv("DATABASE_URL")


@st.cache_resource
def get_engine():
    db_url = get_database_url()
    if db_url:
        return create_engine(db_url, future=True)
    return create_engine(
        f"sqlite:///{DATABASE_PATH}",
        future=True,
        connect_args={"check_same_thread": False},
    )


@st.cache_resource
def get_connection() -> Connection:
    connection = get_engine().connect()
    connection.execute(
        text(
            """CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date TEXT NOT NULL,
                category TEXT NOT NULL,
                user TEXT NOT NULL DEFAULT 'RN',
                amount REAL NOT NULL CHECK(amount > 0),
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
    )
    connection.commit()
    return connection


def get_api_key() -> Optional[str]:
    """Read .env locally or Streamlit secrets after deployment."""
    if key := os.getenv("OPENAI_API_KEY"):
        return key
    try:
        return st.secrets["OPENAI_API_KEY"]
    except (FileNotFoundError, KeyError):
        return None


def get_admin_password() -> str:
    return ADMIN_PASSWORD


def authenticate_app() -> bool:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.login_error = ""

    if st.session_state.logged_in:
        return True

    st.title("🔒 Household Expense Tracker — Login")
    st.write("Enter the admin password to open the app.")
    with st.form("login_form", clear_on_submit=True):
        login_password = st.text_input("Admin password", type="password", key="login_password")
        open_app = st.form_submit_button("Open app")
    if open_app:
        if login_password == get_admin_password():
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
        text("INSERT INTO expenses (transaction_date, category, user, amount, note) VALUES (:date, :category, :user, :amount, :note)"),
        {
            "date": transaction_date.isoformat(),
            "category": category,
            "user": user,
            "amount": amount,
            "note": note.strip(),
        },
    )
    connection.commit()


def update_expense(expense_id: int, transaction_date: date, category: str, user: str, amount: float, note: str) -> None:
    connection = get_connection()
    connection.execute(
        text("UPDATE expenses SET transaction_date = :date, category = :category, user = :user, amount = :amount, note = :note WHERE id = :id"),
        {
            "date": transaction_date.isoformat(),
            "category": category,
            "user": user,
            "amount": amount,
            "note": note.strip(),
            "id": expense_id,
        },
    )
    connection.commit()


def delete_expense(expense_id: int) -> None:
    connection = get_connection()
    connection.execute(text("DELETE FROM expenses WHERE id = :id"), {"id": expense_id})
    connection.commit()


def flush_expenses(start_date: date, end_date: date) -> int:
    connection = get_connection()
    result = connection.execute(
        text("DELETE FROM expenses WHERE transaction_date BETWEEN :start AND :end"),
        {"start": start_date.isoformat(), "end": end_date.isoformat()},
    )
    connection.commit()
    return result.rowcount


def load_expenses(start_date: date, end_date: date, categories: list[str], users: list[str]) -> pd.DataFrame:
    category_placeholders = ", ".join(":cat" + str(i) for i in range(len(categories)))
    user_placeholders = ", ".join(":user" + str(i) for i in range(len(users)))
    query = text(
        f"""SELECT id, transaction_date AS Date, category AS Category, user AS User, amount AS Amount, note AS Note
        FROM expenses WHERE transaction_date BETWEEN :start AND :end AND category IN ({category_placeholders}) AND user IN ({user_placeholders})
        ORDER BY transaction_date DESC, id DESC"""
    )
    params = {"start": start_date.isoformat(), "end": end_date.isoformat()}
    params.update({f"cat{i}": cat for i, cat in enumerate(categories)})
    params.update({f"user{i}": user for i, user in enumerate(users)})
    rows = get_connection().execute(query, params).fetchall()
    return pd.DataFrame(rows, columns=["ID", "Date", "Category", "User", "Amount", "Note"])


def load_latest_expenses(limit: int = 100) -> pd.DataFrame:
    query = text(
        """SELECT id, transaction_date AS Date, category AS Category, user AS User, amount AS Amount, note AS Note
        FROM expenses ORDER BY transaction_date DESC, id DESC LIMIT :limit"""
    )
    rows = get_connection().execute(query, {"limit": limit}).fetchall()
    return pd.DataFrame(rows, columns=["ID", "Date", "Category", "User", "Amount", "Note"])


def get_default_report_start() -> date:
    connection = get_connection()
    row = connection.execute(text("SELECT MIN(transaction_date) FROM expenses")).fetchone()
    if row and row[0]:
        try:
            return date.fromisoformat(row[0])
        except ValueError:
            pass
    today = date.today()
    return today.replace(day=1)


def get_default_report_end() -> date:
    connection = get_connection()
    row = connection.execute(text("SELECT MAX(transaction_date) FROM expenses")).fetchone()
    if row and row[0]:
        try:
            return date.fromisoformat(row[0])
        except ValueError:
            pass
    return date.today()


def report_context(expenses: pd.DataFrame, report_name: str, split_pct: int, actual_rn: float, actual_dk: float, rn_share: float, dk_share: float) -> str:
    """Send a limited snapshot of the selected report to the AI, not the full database."""
    category_totals = expenses.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
    user_totals = expenses.groupby("User", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
    daily_totals = expenses.groupby("Date", as_index=False)["Amount"].sum().sort_values("Date")
    settlement_direction = (
        "RN owes DK" if actual_rn < rn_share else
        "DK owes RN" if actual_rn > rn_share else
        "Settled"
    )
    settlement_amount = abs(actual_rn - rn_share)
    settlement_note = (
        f"DK should pay RN {settlement_amount:.2f}." if actual_rn > rn_share else
        f"RN should pay DK {settlement_amount:.2f}." if actual_rn < rn_share else
        "The report is settled; no payment is due."
    )
    return f"""Report name: {report_name}
Transactions: {len(expenses)}
Total spend: {expenses['Amount'].sum():.2f}
Category totals:\n{category_totals.to_csv(index=False)}
User totals:\n{user_totals.to_csv(index=False)}
Split allocation: RN {split_pct}%, DK {100 - split_pct}%
Target split amounts: RN {rn_share:.2f}, DK {dk_share:.2f}
Actual spent: RN {actual_rn:.2f}, DK {actual_dk:.2f}
Settlement direction: {settlement_direction}
Settlement amount: {settlement_amount:.2f}
Settlement note: {settlement_note}
Daily totals:\n{daily_totals.to_csv(index=False)}
Recent transactions (up to 100):\n{expenses.head(100).to_csv(index=False)}"""


def agent_context(expenses: pd.DataFrame, report_name: str, split_pct: int, actual_rn: float, actual_dk: float, rn_share: float, dk_share: float, latest_transactions: pd.DataFrame) -> str:
    report_text = report_context(expenses, report_name, split_pct, actual_rn, actual_dk, rn_share, dk_share)
    latest_text = latest_transactions.to_csv(index=False) if not latest_transactions.empty else ""
    return (
        report_text
        + "\n\nNOTE: The selected report is the primary context for answering. "
        + "Latest DB transactions are additional context only and may be outside the selected report period.\n"
        + "Latest DB transactions (most recent 100):\n"
        + latest_text
    )


def ask_agent(api_key: str, question: str, context: str) -> str:
    response = OpenAI(api_key=api_key).chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a household-expense analysis assistant. Use only the supplied report data to answer. The selected report is the primary source. Latest DB transactions are additional context only. If the report includes a settlement note, use it directly. If data cannot answer a question, say so. Be concise, use currency-neutral amounts, avoid financial, medical, or tax advice, and end with exactly three useful follow-up questions."},
            {"role": "user", "content": f"REPORT DATA:\n{context}\n\nQUESTION:\n{question}"},
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
    st.caption("Record daily spending, build custom reports, and ask the AI about the selected data.")

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
            st.success("Expense saved.")

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
    total = expenses["Amount"].sum() if not expenses.empty else 0.0
    average = expenses["Amount"].mean() if not expenses.empty else 0.0
    highest = expenses.loc[expenses["Amount"].idxmax(), "Category"] if not expenses.empty else "—"
    col_one, col_two, col_three = st.columns(3)
    col_one.metric("Total spent", f"{total:,.2f}")
    col_two.metric("Transactions", len(expenses))
    col_three.metric("Largest category", highest)

    report_tab, transactions_tab, agent_tab = st.tabs(["Report", "Transactions", "AI expense agent"])
    with report_tab:
        if expenses.empty:
            st.info("No expenses match these filters. Add an expense from the sidebar.")
        else:
            category_totals = expenses.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
            user_totals = expenses.groupby("User", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
            st.bar_chart(category_totals, x="Category", y="Amount")
            st.dataframe(category_totals, hide_index=True, use_container_width=True)
            st.markdown("### Total by user")
            st.dataframe(user_totals, hide_index=True, use_container_width=True)
            st.download_button("Download this report as CSV", data=expenses.to_csv(index=False).encode("utf-8"), file_name="household_expenses_report.csv", mime="text/csv")
            st.caption(f"Average transaction amount: {average:,.2f}")

            split_pct = st.number_input("RN percent share of total", min_value=0, max_value=100, value=40, step=1, format="%d")
            rn_share = total * split_pct / 100
            dk_share = total - rn_share
            split_data = pd.DataFrame(
                [{"User": "RN", "Percent": f"{split_pct}%", "Amount": rn_share}, {"User": "DK", "Percent": f"{100 - split_pct}%", "Amount": dk_share}]
            )
            st.markdown("### Split summary")
            st.dataframe(split_data, hide_index=True, use_container_width=True)
            col_a, col_b = st.columns(2)
            col_a.metric("RN share", f"{rn_share:,.2f}")
            col_b.metric("DK share", f"{dk_share:,.2f}")
            st.caption("The selected percentage is applied to the report total to split expenses between RN and DK.")

            actual_rn = float(user_totals.loc[user_totals["User"] == "RN", "Amount"].sum()) if not user_totals.empty else 0.0
            actual_dk = float(user_totals.loc[user_totals["User"] == "DK", "Amount"].sum()) if not user_totals.empty else 0.0
            rn_diff = actual_rn - rn_share
            dk_diff = actual_dk - dk_share
            if abs(rn_diff) < 0.005:
                settlement = "RN is settled with the target allocation."
            elif rn_diff > 0:
                settlement = f"RN paid {rn_diff:,.2f} more than their target. DK should pay RN {rn_diff:,.2f}."
            else:
                settlement = f"RN paid {abs(rn_diff):,.2f} less than their target. RN should pay DK {abs(rn_diff):,.2f}."

            st.markdown("### Settlement summary")
            st.write(f"Actual RN expense: {actual_rn:,.2f}")
            st.write(f"Actual DK expense: {actual_dk:,.2f}")
            st.write(settlement)

    with transactions_tab:
        st.dataframe(expenses.drop(columns="ID"), hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Edit or delete a selected record")
        if expenses.empty:
            st.info("No records match the current filters.")
        else:
            record_ids = expenses["ID"].tolist()
            selected_id = st.selectbox(
                "Choose a record to edit or delete",
                record_ids,
                format_func=lambda record_id: f"ID {record_id} — {expenses.loc[expenses['ID'] == record_id, 'Date'].iloc[0]} / {expenses.loc[expenses['ID'] == record_id, 'Category'].iloc[0]} / {expenses.loc[expenses['ID'] == record_id, 'Amount'].iloc[0]:.2f}",
            )
            selected = expenses.loc[expenses["ID"] == selected_id].iloc[0]

            with st.form("edit_record_form", clear_on_submit=False):
                edit_date = st.date_input("Transaction date", value=pd.to_datetime(selected["Date"]).date(), key="edit_date")
                edit_category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(selected["Category"]))
                edit_user = st.selectbox("User", USERS, index=USERS.index(selected["User"]))
                edit_amount = st.number_input("Amount", min_value=0.01, step=1.0, value=float(selected["Amount"]), format="%.2f", key="edit_amount")
                edit_note = st.text_input("Note", value=str(selected["Note"]), key="edit_note")
                update_record = st.form_submit_button("Update record")
            if update_record:
                update_expense(selected_id, edit_date, edit_category, edit_user, edit_amount, edit_note)
                st.success("Record updated.")
                rerun_app()

            with st.form("delete_record_form", clear_on_submit=False):
                delete_password = st.text_input("Admin password", type="password", key="delete_password")
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

    with agent_tab:
        st.write("Ask about the report currently selected above. The AI receives only this report’s data.")
        common_questions = [
            "How much should DK pay RN based on the report?",
            "How much will RN get from DK for the selected period?",
            "Which categories cost the most, and what should I review?",
            "How did spending change over the selected period?",
            "What are the largest individual expenses?",
            "Which dates had unusually high spending?",
        ]
        question_choice = st.selectbox("Common questions", ["Write my own question"] + common_questions)
        custom_question = st.text_area("Your question", placeholder="e.g. How much did I spend on grocery and petrol?")
        question = custom_question.strip() or (question_choice if question_choice != "Write my own question" else "")
        if st.button("Ask AI agent", type="primary", disabled=expenses.empty):
            if not question:
                st.warning("Choose a common question or write one of your own.")
            elif not (api_key := get_api_key()):
                st.error("OPENAI_API_KEY is missing. Add it to .env or Streamlit secrets first.")
            else:
                with st.spinner("Reading the selected report…"):
                    try:
                        latest_transactions = load_latest_expenses()
                        answer = ask_agent(
                            api_key,
                            question,
                            agent_context(expenses, report_name, split_pct, actual_rn, actual_dk, rn_share, dk_share, latest_transactions),
                        )
                    except Exception:
                        st.error("The AI agent could not respond. Check the API key and network connection.")
                    else:
                        st.markdown(answer)


if __name__ == "__main__":
    main()
