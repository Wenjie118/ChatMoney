import streamlit as st
from db import save_expense, save_income, get_all_expenses, get_monthly_summary, get_balance, set_balance, get_income

from llm import parse_transaction, get_advice
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date

st.set_page_config(page_title="ChatMoney", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
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
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 1.1rem;
        padding: 0.7rem 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>💰 ChatMoney</h1>
    <p>Your AI-powered personal finance assistant</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["💬 Chat", "🤖 Advisor", "📊 Dashboard"])

with tab1:
    st.header("💬 Chat with Your Financial Assistant")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Welcome message
    if not st.session_state.messages:
        st.info("👋 Welcome! Type transactions like 'spent RM50 on coffee' or 'earned RM5000 salary' to get started!")

    user_input = st.chat_input("e.g., 'Spent RM50 on groceries' or 'Earned RM5000 salary'")

    # Create a container for the chat history
    chat_container = st.container()

    if user_input is not None:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("Saving your transaction..."):
            parsed = parse_transaction(user_input)
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
            lines.append(line)
        response = "\n\n".join(lines)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Draw all messages inside the container AFTER the input
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Clear chat button
    col1, col2, col3 = st.columns([2, 1, 1])
    with col3:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()


            
with tab2:
    st.header("🤖 AI Financial Advisor")
    
    st.markdown("---")
    st.write("Get personalized financial advice based on your spending patterns and habits.")
    
    if st.button("💡 Get Financial Advice", width='stretch', help="Click to receive AI-generated advice"):
        with st.spinner("🔍 Analyzing your spending patterns..."):
            advice = get_advice()
        st.markdown("---")
        st.markdown(advice)
    
    st.markdown("---")
    st.caption("💡 Tip: The more transactions you log, the more accurate and personalized your advice will be!")

with tab3:
    st.header("📊 Spending Dashboard")
    
    st.markdown("---")

    summary = get_monthly_summary()
    expenses = get_all_expenses()
    balance_data = get_balance()
    today = date.today()
    income = get_income(month=today.month, year=today.year)

    st.metric(
        label="Current Balance",
        value=f"RM {balance_data['current_balance']:.2f}"
    )
    st.caption(f"Estimated based on logged transactions since {balance_data['last_updated']}")

    with st.expander("⚙️ Update Manual Balance"):
        amount = st.number_input("Set Manual Balance", min_value=0.0, step=100.0)
        if st.button("Update Balance"):
            set_balance(amount)
            st.success("Balance updated successfully!")
            st.rerun()

    if not expenses:
        st.info("📝 No expenses yet. Add some in the Chat tab to see your dashboard come to life!")
    else:
        # --- Four metric cards side by side with colors ---
        col1, col2, col3, col4 = st.columns(4, gap="medium")
        
        with col1:
            st.metric(
                "💵 Total Income",
                f"RM {summary['total_income']:.2f}",
                delta=f"+RM {summary['total_income']:.2f}",
                delta_color="normal",
                help="Total income for this period"
            )
        
        with col2:
            st.metric(
                "💸 Total Expenses",
                f"RM {summary['total_expenses']:.2f}",
                delta=f"-RM {summary['total_expenses']:.2f}",
                delta_color="inverse",
                help="Total expenses for this period"
            )
        
        with col3:
            st.metric(
                "💰 Net Savings",
                f"RM {summary['net_savings']:.2f}",
                delta=f"RM {summary['net_savings']:.2f}",
                delta_color="normal" if summary['net_savings'] >= 0 else "inverse",
                help="Income minus expenses"
            )

        with col4:
            st.metric(
                "📈 Savings Rate",
                f"{summary['savings_rate']:.1f}%",
                help="Percentage of income saved"
            )
        
        st.markdown("---")
        
        # Build category data once
        by_category = {}
        for expense in expenses:
            if expense["category"] in by_category:
                by_category[expense["category"]] += expense["amount"]
            else:
                by_category[expense["category"]] = expense["amount"]

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("📊 Spending by Category")
            if by_category:
                st.bar_chart(by_category)
            else:
                st.info("No category data available")

        with chart_col2:
            st.subheader("🥧 Expense Distribution")
            if by_category:
                fig, ax = plt.subplots(figsize=(4, 3))
                colors = plt.cm.Set3(range(len(by_category)))
                wedges, texts, autotexts = ax.pie(
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
                st.info("No category data available")
        
        st.markdown("---")

        st.markdown("---")

        # Build income by source
        by_source = {}
        for inc in income:
            source = inc["source"]
            if source in by_source:
                by_source[source] += inc["amount"]
            else:
                by_source[source] = inc["amount"]

        income_col1, income_col2 = st.columns(2)

        with income_col1:
            st.subheader("💵 Income by Source")
            if by_source:
                st.bar_chart(by_source)
            else:
                st.info("No income data available")

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
                st.info("No income data available")
        
        st.subheader("📋 All Expenses")
        df = pd.DataFrame(expenses)
        if 'amount' in df.columns:
            df['amount'] = df['amount'].apply(lambda x: f"RM {x:.2f}")
        
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "category": st.column_config.TextColumn("Category", width="medium"),
                "amount": st.column_config.TextColumn("Amount", width="medium"),
                "date": st.column_config.TextColumn("Date", width="medium"),
                "description": st.column_config.TextColumn("Description", width="large")
            }
        )
