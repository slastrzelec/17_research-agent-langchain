import sys
import types
from dataclasses import dataclass, field

import pytest
from streamlit.testing.v1 import AppTest


@dataclass
class AgentResult:  # mirrors agent.AgentResult; the real agent module is stubbed in these tests
    answer: str = ""
    steps: list = field(default_factory=list)
    tools_used: list = field(default_factory=list)
    tokens: int = 0
    sources: list = field(default_factory=list)


APP = __file__.replace("tests/test_app.py", "app.py").replace("tests\\test_app.py", "app.py")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_AGENT_DB", str(tmp_path / "app.db"))
    calls = []

    def fake_run_agent(question, history=None, model="gpt-4o-mini"):
        calls.append((question, model))
        return AgentResult(
            answer=f"answer to {question}",
            steps=["🔧 Using tool: `calculate` with query: `{}`"],
            tools_used=["calculate"], tokens=100,
            sources=[{"title": "<b>Paper</b>", "url": "https://arxiv.org/abs/1"}] + [
                {"title": f"Wiki {i}", "url": f"https://en.wikipedia.org/wiki/W{i}"} for i in range(4)],
        )

    stub = types.ModuleType("agent")
    stub.AgentResult = AgentResult
    stub.run_agent = fake_run_agent
    monkeypatch.setitem(sys.modules, "agent", stub)
    at = AppTest.from_file(APP, default_timeout=30)
    at.calls = calls
    return at.run()


def _html(at):
    """Everything that Streamlit would interpret as HTML (allow_html=True elements only)."""
    return " ".join(m.value for m in at.markdown if m.allow_html)


def test_starts_without_errors(app):
    assert not app.exception


def test_html_in_question_and_answer_is_escaped(app):
    app.chat_input[0].set_value("<script>alert(1)</script>").run()
    assert not app.exception
    html = _html(app)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_too_long_question_is_rejected_without_calling_agent(app):
    app.chat_input[0].set_value("x" * 1001).run()
    assert app.calls == []
    assert any("too long" in w.value for w in app.warning)


def test_stats_and_recent_queries_only_for_own_session(app):
    app.chat_input[0].set_value("2+2").run()
    assert app.calls == [("2+2", "gpt-4o-mini")]
    assert [m.value for m in app.sidebar.metric][0] == "1"
    import database
    database.save_conversation("someone-else", "SECRET question", "x", [], 1)
    app.run()
    assert "SECRET" not in " ".join(e.label for e in app.sidebar.expander)
    assert [m.value for m in app.sidebar.metric][0] == "1"


def test_agent_exception_shows_friendly_error(app, monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail sk-123")
    sys.modules["agent"].run_agent = boom
    app.chat_input[0].set_value("hi").run()
    assert any("RuntimeError" in e.value and "sk-123" not in e.value for e in app.error)
    # ...but the traceback is logged on the server, so failures can be diagnosed
    assert any("Agent call failed" in r.getMessage() and r.exc_info for r in caplog.records)


def test_sources_are_rendered_as_escaped_links(app):
    app.chat_input[0].set_value("hello").run()
    html = _html(app)
    assert 'href="https://arxiv.org/abs/1"' in html
    assert "&lt;b&gt;Paper&lt;/b&gt;" in html and "<b>Paper</b>" not in html
    assert 'rel="noopener noreferrer"' in html


def test_answer_is_rendered_without_html_and_without_images(app):
    app.chat_input[0].set_value("hello").run()
    answers = [m for m in app.markdown if m.value.startswith("answer to")]
    assert answers and all(not m.allow_html for m in answers)


def test_sources_are_grouped_and_overflow_is_collapsed(app):
    app.chat_input[0].set_value("hello").run()
    html = _html(app)
    assert "📖 Wikipedia" in html and "📄 ArXiv" in html
    assert "Wiki 0" in html and "Wiki 1" in html          # first two shown directly
    labels = [e.label for e in app.expander]
    assert "More 📖 Wikipedia sources (2)" in labels      # the other two are collapsed
