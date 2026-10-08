import sqlite3
from datetime import datetime, timedelta

import pytest
import database as db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_AGENT_DB", str(tmp_path / "t.db"))
    db.init_db()


def test_sessions_are_isolated():
    db.save_conversation("A", "qa", "aa", ["wikipedia"], 10)
    db.save_conversation("B", "qb", "ab", [], 5)
    a, b = db.get_conversations("A"), db.get_conversations("B")
    assert [r[1] for r in a] == ["qa"] and [r[1] for r in b] == ["qb"]
    assert b[0][3] == "none"
    assert db.get_conversations("C") == []


def test_newest_first_and_sql_injection_is_inert():
    db.save_conversation("A", "first", "x", [], 1)
    db.save_conversation("A", "'); DROP TABLE conversations;--", "y", [], 1)
    rows = db.get_conversations("A")
    assert rows[0][1].startswith("'); DROP") and rows[1][1] == "first"
    assert db.get_conversations("A' OR '1'='1") == []


def test_migration_from_first_version_and_legacy_rows_hidden(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
                 "question TEXT NOT NULL, answer TEXT NOT NULL, tools_used TEXT, tokens_used INTEGER)")
    conn.execute("INSERT INTO conversations (timestamp, question, answer, tools_used, tokens_used) VALUES (?,?,?,?,?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "old q", "old a", "none", 1))
    conn.commit(); conn.close()
    monkeypatch.setenv("RESEARCH_AGENT_DB", str(path))
    db.init_db()
    db.save_conversation("S", "new", "a", [], 1)
    assert [r[1] for r in db.get_conversations("S")] == ["new"]
    assert db.get_conversations(None) == []  # NULL session rows are never returned


def test_retention_purge(tmp_path):
    old = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO conversations (timestamp, question, answer, tools_used, tokens_used, session_id) "
                 "VALUES (?,?,?,?,?,?)", (old, "ancient", "a", "none", 1, "A"))
    conn.commit(); conn.close()
    db.save_conversation("A", "fresh", "a", [], 1)
    db.init_db()
    assert [r[1] for r in db.get_conversations("A")] == ["fresh"]
