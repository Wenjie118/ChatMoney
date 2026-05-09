import streamlit as st
from db import save_expense, save_income, get_all_expenses, get_monthly_summary
from llm import parse_transaction, get_advice

st.set_page_config(page_title="ChatMoney", layout="wide")

tab1, tab2, tab3 = st.tabs(["💬 Chat", "🤖 Advisor", "📊 Dashboard"])

with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    user_input = st.chat_input("Type your expense here...")

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
                line = f"✅ Saved Income: RM{transaction['amount']} from {transaction['source']}"
            elif transaction["type"] == "expense":
                line = f"✅ Saved Expense: RM{transaction['amount']} on {transaction['category']}"
            lines.append(line)
        response = "\n".join(lines)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Draw all messages inside the container AFTER the input
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

            
with tab2:
    st.header("🤖 AI Financial Advisor")

    if st.button("Get Advice"):
        with st.spinner("Analyzing your spending..."):
            advice = get_advice()
        st.markdown(advice)

with tab3:
    st.header("📊 Spending Dashboard")

    summary = get_monthly_summary()
    expenses = get_all_expenses()

    if not expenses:
        st.info("No expenses yet. Add some in the Chat tab!")
    else:
        # --- Four metric cards side by side ---
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Income", f"RM {summary['total_income']:.2f}")
        with col2:
            st.metric("Total Expenses", f"RM {summary['total_expenses']:.2f}")
        with col3:
            st.metric("Net Savings", f"RM {summary['net_savings']:.2f}")
        with col4:
            st.metric("Savings Rate", f"{summary['savings_rate']:.1f}%")

        # --- Bar chart by category ---
        by_category = {}
        for expense in expenses:
            if expense["category"] in by_category:
                by_category[expense["category"]] += expense["amount"]
            else:
                by_category[expense["category"]] = expense["amount"]

        st.subheader("Spending by Category")
        st.bar_chart(by_category)

        # --- Full expense table ---
        st.subheader("All Expenses")
        st.dataframe(expenses)

