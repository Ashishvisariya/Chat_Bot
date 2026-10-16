import streamlit as st

from backend import (
    create_chat,
    get_all_chats,
    get_chat_messages,
    chat_exists,
    stream_response,
)

st.set_page_config(
    page_title="LangGraph Chatbot",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 My LangGraph Chatbot")
st.caption("Powered by LangGraph and Groq")

if "active_thread_id" not in st.session_state:
    st.session_state["active_thread_id"] = None


# Select a valid conversation on startup.
chats = get_all_chats()
if not chats:
    st.session_state["active_thread_id"] = create_chat()
elif (
    st.session_state["active_thread_id"] is None
    or not chat_exists(st.session_state["active_thread_id"])
):
    st.session_state["active_thread_id"] = chats[0]["thread_id"]


with st.sidebar:
    st.title("💬 Chat History")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state["active_thread_id"] = create_chat()
        st.rerun()

    st.divider()
    chats = get_all_chats()
    if not chats:
        st.caption("No conversations yet.")

    for chat in chats:
        thread_id = chat["thread_id"]
        title = chat["title"] or "New Chat"
        label = f"● {title}" if thread_id == st.session_state["active_thread_id"] else title
        if st.button(label, key=f"select_{thread_id}", use_container_width=True):
            st.session_state["active_thread_id"] = thread_id
            st.rerun()

    st.divider()
    st.caption("Current Thread ID")
    st.code(st.session_state["active_thread_id"], language=None)

active_thread_id = st.session_state["active_thread_id"]
chats = get_all_chats()
active_chat = next((c for c in chats if c["thread_id"] == active_thread_id), None)
st.subheader(active_chat["title"] if active_chat else "New Chat")

for message in get_chat_messages(active_thread_id):
    if message["role"] in ("user", "assistant"):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

user_input = st.chat_input("Type your message...")
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            st.write_stream(
                stream_response(user_input=user_input, thread_id=active_thread_id)
            )
        except Exception as error:
            st.error(f"Something went wrong: {error}")

    st.rerun()
