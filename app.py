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

        # 2. Call parser, build response string
        parsed = parse_expense(user_input)
        lines = []
        for expense in parsed:
            line = f"✅ Saved: RM{expense['amount']} on {expense['category']} — {expense['description']}"
            lines.append(line)
        response = "\n".join(lines)

        # 3. Save assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})

        # 4. Display the new messages
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            st.markdown(response)

with tab2:
    pass

with tab3:
    pass