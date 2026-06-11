import streamlit as st
from db import (
    save_expense,
    save_income,
    save_multiple_transactions,
    get_expenses,
    get_balance,
    set_balance,
    get_income,
    get_logged_periods,
    check_supabase_connection,
    DatabaseConnectionError,
)

from llm import parse_transaction, parse_pdf_transactions, get_advice
import pandas as pd
import matplotlib.pyplot as plt
import calendar
from datetime import date
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="ChatMoney", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 14px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.25);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1rem;
        opacity: 0.9;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 1.05rem;
        padding: 0.7rem 1.5rem;
        border-radius: 10px 10px 0 0;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(102,126,234,0.12), rgba(118,75,162,0.12));
    }

    /* Buttons */
    .stButton button {
        border-radius: 10px;
        font-weight: 600;
        transition: transform 0.05s ease, box-shadow 0.15s ease;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.25);
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f5f7fa 0%, #e6ecf7 100%);
        padding: 1rem 1.25rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }

    /* Bordered containers act as clean "cards" */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px;
    }

    /* Full-screen processing overlay (freezes the whole page) */
    .cm-overlay {
        position: fixed;
        inset: 0;
        background: rgba(15, 17, 26, 0.55);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .cm-overlay-box {
        background: #ffffff;
        padding: 2rem 2.75rem;
        border-radius: 18px;
        box-shadow: 0 16px 50px rgba(0, 0, 0, 0.35);
        text-align: center;
        max-width: 340px;
    }
    .cm-spinner {
        width: 52px;
        height: 52px;
        margin: 0 auto 1.1rem;
        border: 5px solid #e7e9f3;
        border-top-color: #667eea;
        border-radius: 50%;
        animation: cm-spin 0.9s linear infinite;
    }
    @keyframes cm-spin { to { transform: rotate(360deg); } }
    .cm-overlay-box p { margin: 0; font-weight: 600; color: #2b2b3a; }
    .cm-overlay-box span { font-size: 0.85rem; color: #888; }

    /* Cancellable processing modal (backdrop + centered Streamlit box) */
    .cm-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(15, 17, 26, 0.55);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        z-index: 99990;
    }
    .st-key-cm_modal {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 99999;
        width: 360px;
        max-width: 90vw;
        background: #ffffff;
        padding: 1.75rem 2rem 1.5rem;
        border-radius: 18px;
        box-shadow: 0 16px 50px rgba(0, 0, 0, 0.35);
        text-align: center;
    }
    .cm-modal-title { margin: 0; font-weight: 700; color: #2b2b3a; font-size: 1.05rem; }
    .cm-modal-sub { display: block; margin-top: 0.25rem; font-size: 0.82rem; color: #888; }
</style>
""", unsafe_allow_html=True)

# Reusable full-screen overlay shown while the AI works (blocks all interaction)
PROCESSING_OVERLAY = """
<div class="cm-overlay">
    <div class="cm-overlay-box">
        <div class="cm-spinner"></div>
        <p>{title}</p>
        <span>{subtitle}</span>
    </div>
</div>
"""

# Header
st.markdown("""
<div class="main-header">
    <h1>💰 ChatMoney</h1>
    <p>Your AI-powered personal finance assistant</p>
</div>
""", unsafe_allow_html=True)

db_ok, db_error = check_supabase_connection()
if not db_ok:
    st.error("Database connection problem")
    st.markdown(db_error)

def consolidate_transactions(transactions):
    """Merge identical transactions (same type/description/category) regardless of
    date: sum their amounts and count how many rows were combined.

    The representative date kept is the latest one among the merged rows.
    """
    grouped = {}
    for t in transactions:
        cat = t.get("category") or t.get("source")
        key = (t.get("type"), t.get("description"), cat)
        d = t.get("date")
        if key in grouped:
            g = grouped[key]
            g["Amount"] += t.get("amount", 0)
            g["Count"] += 1
            if d and (g["Date"] is None or str(d) > str(g["Date"])):
                g["Date"] = d
        else:
            grouped[key] = {
                "Date": d,
                "Type": t.get("type"),
                "Description": t.get("description"),
                "Category/Source": cat,
                "Count": 1,
                "Amount": t.get("amount", 0),
            }
    return list(grouped.values())


@st.cache_resource
def get_executor():
    """A shared thread pool so PDF parsing runs off the script thread (cancellable)."""
    return ThreadPoolExecutor(max_workers=2)


def _finish_pdf_parse(future):
    """Pull the result from a finished parse future into session state."""
    st.session_state["pdf_processing"] = False
    st.session_state["pdf_future"] = None
    st.session_state["pdf_pending_name"] = None
    try:
        parsed_pdf = future.result()
    except ValueError as e:
        st.session_state["pdf_error"] = str(e)
        st.session_state["pdf_uploader_key"] += 1  # reset uploader so user can re-upload
        return
    consolidated = consolidate_transactions(parsed_pdf)
    preview = pd.DataFrame(consolidated).reindex(
        columns=["Date", "Type", "Description", "Category/Source", "Count", "Amount"]
    )
    preview.insert(0, "Delete", False)
    st.session_state["pdf_preview_df"] = preview
    st.session_state["pdf_parsed_name"] = st.session_state.get("pdf_pending_name")


def _cancel_pdf_parse():
    """Abandon the in-flight parse and reset the uploader for a fresh upload."""
    st.session_state["pdf_processing"] = False
    st.session_state["pdf_future"] = None
    st.session_state["pdf_pending_name"] = None
    st.session_state["pdf_uploader_key"] += 1


@st.fragment(run_every="0.7s")
def pdf_processing_modal():
    """Full-screen modal shown while a PDF is parsed in the background.

    Runs every 0.7s on its own (without rerunning the whole app) to check whether
    the background parse has finished, and offers a Stop/Cancel button on top of a
    page-blocking backdrop.
    """
    future = st.session_state.get("pdf_future")

    st.markdown('<div class="cm-backdrop"></div>', unsafe_allow_html=True)
    with st.container(key="cm_modal"):
        st.markdown(
            '<div class="cm-spinner"></div>'
            '<p class="cm-modal-title">🤖 Reading your statement…</p>'
            '<span class="cm-modal-sub">Extracting transactions. You can stop and re-upload anytime.</span>',
            unsafe_allow_html=True,
        )
        if st.button("🛑 Stop / Cancel", key="cm_cancel_btn", width="stretch"):
            _cancel_pdf_parse()
            st.rerun(scope="app")

    if future is not None and future.done():
        _finish_pdf_parse(future)
        st.rerun(scope="app")


tab1, tab2, tab3 = st.tabs(["💬 Chat", "🤖 Advisor", "📊 Dashboard"])

with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── Section 1: Import a bank statement ─────────────────────────────────
    if "pdf_uploader_key" not in st.session_state:
        st.session_state["pdf_uploader_key"] = 0

    with st.container(border=True):
        imp_left, imp_right = st.columns([3, 2], vertical_alignment="center")
        with imp_left:
            st.markdown("#### 📄 Import a bank statement")
            st.caption(
                "Upload a Malaysian bank statement PDF and the AI will extract every "
                "transaction into an editable table before anything is saved."
            )
        with imp_right:
            uploaded_pdf = st.file_uploader(
                "Bank statement PDF",
                type=["pdf"],
                key=f"pdf_uploader_{st.session_state['pdf_uploader_key']}",
                label_visibility="collapsed",
            )

        # Surface a parse error from a previous attempt
        if st.session_state.get("pdf_error"):
            st.error(f"⚠️ {st.session_state.pop('pdf_error')}")

        # Kick off a background parse for a freshly uploaded file
        if (uploaded_pdf is not None
                and not st.session_state.get("pdf_processing")
                and st.session_state.get("pdf_preview_df") is None):
            st.session_state["pdf_processing"] = True
            st.session_state["pdf_pending_name"] = uploaded_pdf.name
            st.session_state["pdf_future"] = get_executor().submit(
                parse_pdf_transactions, uploaded_pdf.getvalue()
            )
            st.rerun()

        # While parsing: show the cancellable modal that polls the background thread
        if st.session_state.get("pdf_processing"):
            pdf_processing_modal()

        # Editable preview of parsed transactions
        if st.session_state.get("pdf_preview_df") is not None:
            st.divider()
            st.markdown("##### ✏️ Review & edit")
            st.caption(
                "Tick **🗑️** to remove a row, edit any cell, or scroll to the bottom to add new rows. "
                "**Count** shows how many statement lines were merged into that row. "
                "Nothing is saved until you confirm."
            )
            edited_df = st.data_editor(
                st.session_state["pdf_preview_df"],
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                key="pdf_editor",
                column_config={
                    "Delete": st.column_config.CheckboxColumn("🗑️", help="Tick to remove this row", default=False, width="small"),
                    "Date": st.column_config.TextColumn("Date"),
                    "Type": st.column_config.SelectboxColumn("Type", options=["expense", "income"]),
                    "Description": st.column_config.TextColumn("Description", width="large"),
                    "Category/Source": st.column_config.TextColumn("Category/Source"),
                    "Count": st.column_config.NumberColumn("Count", help="Number of merged statement lines", disabled=True, width="small"),
                    "Amount": st.column_config.NumberColumn("Amount", format="RM %.2f", min_value=0.0),
                },
            )

            save_col, cancel_col, _ = st.columns([1, 1, 2])
            with save_col:
                confirm_save = st.button("✅ Confirm & Save", key="pdf_confirm_save", width="stretch", type="primary")
            with cancel_col:
                if st.button("✖️ Discard", key="pdf_discard", width="stretch"):
                    st.session_state["pdf_preview_df"] = None
                    st.session_state["pdf_parsed_name"] = None
                    st.session_state["pdf_uploader_key"] += 1
                    st.rerun()

            if confirm_save:
                txns = []
                for row in edited_df.to_dict("records"):
                    if row.get("Delete"):
                        continue
                    amt = row.get("Amount")
                    # Skip removed/blank rows (e.g. empty rows added at the bottom)
                    if not row.get("Type") or pd.isna(amt):
                        continue
                    txns.append({
                        "type": row.get("Type"),
                        "amount": amt,
                        "category": row.get("Category/Source"),
                        "date": row.get("Date"),
                        "description": row.get("Description"),
                    })
                overlay = st.empty()
                overlay.markdown(
                    PROCESSING_OVERLAY.format(
                        title="💾 Saving transactions…",
                        subtitle="Writing your transactions to the database.",
                    ),
                    unsafe_allow_html=True,
                )
                try:
                    result = save_multiple_transactions(txns)
                except DatabaseConnectionError as e:
                    overlay.empty()
                    st.error(str(e))
                else:
                    msg = f"✅ Saved {result['saved']} of {result['total']} transactions"
                    if result["failed"]:
                        msg += f" ({result['failed']} failed)"
                    st.session_state["pdf_preview_df"] = None
                    st.session_state["pdf_parsed_name"] = None
                    st.session_state["pdf_uploader_key"] += 1
                    st.session_state["pdf_save_msg"] = msg
                    overlay.empty()
                    st.rerun()

    # One-time success banner after a save+rerun
    if st.session_state.get("pdf_save_msg"):
        st.success(st.session_state.pop("pdf_save_msg"))

    # ── Section 2: Chat ────────────────────────────────────────────────────
    st.markdown("#### 💬 Chat with your assistant")

    # Welcome message
    if not st.session_state.messages:
        st.info("👋 Type transactions like *'spent RM50 on coffee'* or *'earned RM5000 salary'* to log them instantly.")

    user_input = st.chat_input(
        "e.g., 'Spent RM50 on groceries' or 'Earned RM5000 salary'",
        disabled=st.session_state.get("pdf_processing", False),
    )

    if user_input is not None:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("Saving your transaction..."):
            try:
                parsed = parse_transaction(user_input)
            except ValueError as e:
                parsed = []
                response = f"⚠️ {e}"
            else:
                try:
                    for transaction in parsed:
                        if transaction["type"] == "income":
                            save_income(
                                amount=transaction["amount"],
                                source=transaction["source"],
                                income_date=transaction["date"],
                                desc=transaction.get("description")
                            )
                        elif transaction["type"] == "expense":
                            save_expense(
                                amount=transaction["amount"],
                                category=transaction["category"],
                                expense_date=transaction["date"],
                                desc=transaction.get("description")
                            )

                    lines = []
                    for transaction in parsed:
                        if transaction["type"] == "income":
                            line = f"✅ **Saved Income:** RM{transaction['amount']} from {transaction['source']}"
                        elif transaction["type"] == "expense":
                            line = f"✅ **Saved Expense:** RM{transaction['amount']} on {transaction['category']}"
                        else:
                            continue
                        lines.append(line)
                    response = "\n\n".join(lines) if lines else (
                        "⚠️ I couldn't find any transactions in that message. "
                        "Try something like 'Spent RM50 on groceries' or 'Earned RM5000 salary'."
                    )
                except DatabaseConnectionError as e:
                    response = f"⚠️ **Could not save to database.**\n\n{e}"

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    _, _, col3 = st.columns([2, 1, 1])
    with col3:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()


with tab2:
    st.markdown("#### 🤖 AI Financial Advisor")

    with st.container(border=True):
        try:
            periods = get_logged_periods()
        except DatabaseConnectionError as e:
            periods = []
            st.error(str(e))

        if not periods:
            st.info("📝 No transactions logged yet. Add some in the Chat tab to get personalized advice!")
        else:
            st.write("Choose a month you've logged transactions for and get tailored advice on it.")
            sel_period = st.selectbox(
                "Month to analyze",
                periods,
                format_func=lambda p: date(p[0], p[1], 1).strftime("%B %Y"),
            )

            if st.button("💡 Get Financial Advice", width='stretch', type="primary", help="Click to receive AI-generated advice"):
                period_label = date(sel_period[0], sel_period[1], 1).strftime("%B %Y")
                with st.spinner(f"🔍 Analyzing your spending for {period_label}..."):
                    try:
                        advice = get_advice(month=sel_period[1], year=sel_period[0])
                    except (DatabaseConnectionError, ValueError) as e:
                        st.error(str(e))
                    else:
                        st.session_state["latest_advice"] = advice
                        st.session_state["latest_advice_period"] = period_label

            if st.session_state.get("latest_advice"):
                with st.container(border=True):
                    if st.session_state.get("latest_advice_period"):
                        st.caption(f"📅 Advice for **{st.session_state['latest_advice_period']}**")
                    st.markdown(st.session_state["latest_advice"])

    st.caption("💡 Tip: The more transactions you log, the more accurate and personalized your advice will be!")

with tab3:
    st.markdown("#### 📊 Spending Dashboard")

    if not db_ok:
        st.stop()

    try:
        balance_data = get_balance()
    except DatabaseConnectionError as e:
        st.error(str(e))
        st.stop()

    with st.container(border=True):
        bal_col, upd_col = st.columns([2, 1], vertical_alignment="center")
        with bal_col:
            st.metric(
                label="💰 Current Balance",
                value=f"RM {balance_data['current_balance']:.2f}"
            )
            st.caption(f"Estimated from logged transactions since {balance_data['last_updated']}")
        with upd_col:
            with st.popover("⚙️ Update balance", width="stretch"):
                amount = st.number_input("Set Manual Balance", min_value=0.0, step=100.0)
                if st.button("Update Balance", type="primary"):
                    set_balance(amount)
                    st.success("Balance updated successfully!")
                    st.rerun()

    # Month/year picker — only offer years/months that actually have logged data,
    # and only the months that have data for the chosen year.
    try:
        periods = get_logged_periods()
    except DatabaseConnectionError as e:
        st.error(str(e))
        st.stop()

    if not periods:
        st.info("📝 No transactions logged yet. Add some in the Chat tab to see your dashboard!")
        st.stop()

    # Map each year that has data to the sorted list of months that have data.
    months_by_year = {}
    for y, m in periods:
        months_by_year.setdefault(y, []).append(m)
    for y in months_by_year:
        months_by_year[y] = sorted(months_by_year[y])

    year_options = sorted(months_by_year, reverse=True)

    pick_col1, pick_col2, _ = st.columns([1, 1, 2])
    # Year first in code so the month options can depend on the selected year.
    with pick_col2:
        sel_year = st.selectbox("Year", year_options, index=0)
    with pick_col1:
        month_options = months_by_year[sel_year]
        sel_month = st.selectbox(
            "Month",
            month_options,
            format_func=lambda m: calendar.month_name[m],
        )

    try:
        income = get_income(month=sel_month, year=sel_year)
        expenses = get_expenses(month=sel_month, year=sel_year)
    except DatabaseConnectionError as e:
        st.error(str(e))
        st.stop()

    total_income = sum(i["amount"] for i in income)
    total_expenses = sum(e["amount"] for e in expenses)
    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

    month_label = date(sel_year, sel_month, 1).strftime("%B %Y")
    st.caption(f"📅 Showing data for **{month_label}**")

    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        st.metric(
            "💵 Total Income",
            f"RM {total_income:.2f}",
            delta=f"+RM {total_income:.2f}",
            delta_color="normal",
            help=f"Total income for {month_label}"
        )

    with col2:
        st.metric(
            "💸 Total Expenses",
            f"RM {total_expenses:.2f}",
            delta=f"-RM {total_expenses:.2f}",
            delta_color="inverse",
            help=f"Total expenses for {month_label}"
        )

    with col3:
        st.metric(
            "💰 Net Savings",
            f"RM {net_savings:.2f}",
            delta=f"RM {net_savings:.2f}",
            delta_color="normal" if net_savings >= 0 else "inverse",
            help="Income minus expenses"
        )

    with col4:
        st.metric(
            "📈 Savings Rate",
            f"{savings_rate:.1f}%",
            help="Percentage of income saved"
        )

    if not expenses and not income:
        st.info(f"📝 No transactions for {month_label}. Try another month, or add some in the Chat tab!")

    st.markdown("---")

    by_category = {}
    for expense in expenses:
        by_category[expense["category"]] = by_category.get(expense["category"], 0) + expense["amount"]

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("📊 Spending by Category")
        if by_category:
            st.bar_chart(by_category)
        else:
            st.info("No expenses logged this month")

    with chart_col2:
        st.subheader("🥧 Expense Distribution")
        if by_category:
            fig, ax = plt.subplots(figsize=(4, 3))
            colors = plt.cm.Set3(range(len(by_category)))
            ax.pie(
                by_category.values(),
                labels=by_category.keys(),
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
                pctdistance=0.75,
                labeldistance=1.15,
                textprops={'fontsize': 8}
            )
            ax.set_title('Expense Distribution by Category', fontsize=9)
            plt.tight_layout()
            st.pyplot(fig, width='content')
        else:
            st.info("No expenses logged this month")

    st.markdown("---")

    by_source = {}
    for inc in income:
        by_source[inc["source"]] = by_source.get(inc["source"], 0) + inc["amount"]

    income_col1, income_col2 = st.columns(2)

    with income_col1:
        st.subheader("💵 Income by Source")
        if by_source:
            st.bar_chart(by_source)
        else:
            st.info("No income logged this month")

    with income_col2:
        st.subheader("🥧 Income Distribution")
        if by_source:
            fig2, ax2 = plt.subplots(figsize=(4, 3))
            colors2 = plt.cm.Set3(range(len(by_source)))
            ax2.pie(
                by_source.values(),
                labels=by_source.keys(),
                autopct='%1.1f%%',
                colors=colors2,
                startangle=90,
                pctdistance=0.75,
                labeldistance=1.15,
                textprops={'fontsize': 8}
            )
            ax2.set_title('Income Distribution by Source', fontsize=9)
            plt.tight_layout()
            st.pyplot(fig2, width='content')
        else:
            st.info("No income logged this month")

    st.subheader(f"📋 Expenses for {month_label}")
    if expenses:
        df = pd.DataFrame(expenses)

        # Sort latest → oldest and show Date as the first column
        if 'date' in df.columns:
            df = df.sort_values('date', ascending=False)
            df = df[['date'] + [c for c in df.columns if c != 'date']]

        if 'amount' in df.columns:
            df['amount'] = df['amount'].apply(lambda x: f"RM {x:.2f}")

        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "date": st.column_config.TextColumn("Date", width="medium"),
                "category": st.column_config.TextColumn("Category", width="medium"),
                "amount": st.column_config.TextColumn("Amount", width="medium"),
                "description": st.column_config.TextColumn("Description", width="large")
            }
        )
    else:
        st.info("No expenses logged this month")
