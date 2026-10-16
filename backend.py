import os
import sqlite3
import uuid
from pathlib import Path
from typing import TypedDict, Annotated

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

load_dotenv()

# Render persistent disk path is configured through DATABASE_PATH.
# Locally, the database is stored next to this file.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "chat_history.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY is missing. Add it to your local .env or Render Environment settings."
    )

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    api_key=api_key,
    temperature=0,
    streaming=True,
)


def get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, id)")


init_db()


def create_chat():
    thread_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (thread_id, title) VALUES (?, ?)",
            (thread_id, "New Chat"),
        )
    return thread_id


def get_all_chats():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT thread_id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def chat_exists(thread_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    return row is not None


def get_chat_messages(thread_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE thread_id = ? ORDER BY id ASC",
            (thread_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_message(thread_id, role, content):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
            (thread_id, role, content),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?",
            (thread_id,),
        )


def update_chat_title(thread_id, title):
    title = " ".join(title.split())[:45] or "New Chat"
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE thread_id = ? AND title = 'New Chat'",
            (title, thread_id),
        )


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]


def chat_node(state: ChatState):
    return {"messages": [llm.invoke(state["messages"])]}


builder = StateGraph(ChatState)
builder.add_node("chat_node", chat_node)
builder.add_edge(START, "chat_node")
builder.add_edge("chat_node", END)
workflow = builder.compile()


def stream_response(user_input: str, thread_id: str):
    if not chat_exists(thread_id):
        raise ValueError("Chat not found. Please create a new chat.")

    previous_messages = get_chat_messages(thread_id)
    if not previous_messages:
        update_chat_title(thread_id, user_input)

    messages = []
    for item in previous_messages:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        else:
            messages.append(AIMessage(content=item["content"]))

    # Save the user's turn before generation so it survives app reruns.
    save_message(thread_id, "user", user_input)
    messages.append(HumanMessage(content=user_input))

    full_response = ""
    try:
        for chunk, metadata in workflow.stream(
            {"messages": messages},
            stream_mode="messages",
        ):
            if metadata.get("langgraph_node") != "chat_node":
                continue
            content = chunk.content
            if isinstance(content, str) and content:
                full_response += content
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if text:
                            full_response += text
                            yield text
    except Exception:
        # Keep the user prompt, but don't store a partial assistant response.
        raise

    if full_response:
        save_message(thread_id, "assistant", full_response)
