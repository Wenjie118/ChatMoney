import streamlit as st
from db import get_all_expenses
from llm import parse_expense, get_advice

st.set_page_config(page_title="ChatMoney", layout="wide")

tab1, tab2, tab3 = st.tabs(["💬 Chat", "🤖 Advisor", "📊 Dashboard"])

with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Type your expense here...")

    if user_input is not None:
        # 1. Save user message to history
        st.session_state.messages.append({"role": "user", "content": user_input})

        # 2. Call parser with spinner — this is the slow part
        with st.spinner("Saving your expense..."):
            parsed = parse_expense(user_input)

        # 3. Show success message — runs after spinner completes
        st.success("Expenses saved successfully!")

        # 4. Build response string
        lines = []
        for expense in parsed:
            line = f"✅ Saved: RM{expense['amount']} on {expense['category']} — {expense['description']}"
            lines.append(line)
        response = "\n".join(lines)

        # 5. Save assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})

        # 6. Display the new messages
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            st.markdown(response)

            
with tab2:
    st.header("🤖 AI Financial Advisor")

    if st.button("Get Advice"):
        with st.spinner("Analyzing your spending..."):
            advice = get_advice(get_all_expenses())
        st.markdown(advice)

with tab3:
    st.header("📊 Spending Dashboard")

    expenses = get_all_expenses()
    if not expenses:
        st.info("No expenses yet. Add some in the Chat tab!")
    else:
        total_amount = 0
        for expense in expenses:
            total_amount += expense["amount"]
        
        st.metric("Total Spent", f"RM {total_amount:.2f}")

        by_category = {}

        for expense in expenses:
            if expense["category"] in by_category:
                by_category[expense["category"]] += expense["amount"]
            else:
                by_category[expense["category"]] = expense["amount"]
        
        st.bar_chart(by_category)
        st.subheader("All Expenses")
        st.dataframe(expenses)

