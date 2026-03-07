import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "research_agent.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            tools_used TEXT,
            tokens_used INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_conversation(question: str, answer: str, tools_used: list, tokens_used: int = 0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversations (timestamp, question, answer, tools_used, tokens_used)
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        question,
        answer,
        ", ".join(tools_used) if tools_used else "none",
        tokens_used
    ))
    conn.commit()
    conn.close()

def get_all_conversations():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows