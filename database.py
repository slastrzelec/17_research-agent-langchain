import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta

RETENTION_DAYS = 30
_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "research_agent.db")


def _db_path() -> str:
    # Overridable (tests use a temporary file).
    return os.environ.get("RESEARCH_AGENT_DB", _DEFAULT_PATH)


def _connect():
    return closing(sqlite3.connect(_db_path()))


def init_db(retention_days: int = RETENTION_DAYS):
    """Create the table, migrate old schemas and purge rows past the retention period."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                tools_used TEXT,
                tokens_used INTEGER,
                session_id TEXT
            )
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)")]
        if "session_id" not in cols:  # databases created by the first version
            conn.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT")
        cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
        conn.commit()


def save_conversation(session_id: str, question: str, answer: str,
                      tools_used: list, tokens_used: int = 0):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (timestamp, question, answer, tools_used, tokens_used, session_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                question,
                answer,
                ", ".join(tools_used) if tools_used else "none",
                tokens_used,
                session_id,
            ),
        )
        conn.commit()


def get_conversations(session_id: str):
    """Rows of ONE session, newest first: (timestamp, question, answer, tools_used, tokens_used)."""
    with _connect() as conn:
        return conn.execute(
            "SELECT timestamp, question, answer, tools_used, tokens_used "
            "FROM conversations WHERE session_id = ? ORDER BY id DESC",
            (session_id,),
        ).fetchall()
