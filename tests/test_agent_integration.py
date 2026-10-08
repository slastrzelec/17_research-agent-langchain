import pytest
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError

import agent as agent_mod
import tools as tools_mod
from fakes import ScriptedChatModel, answer_msg, tool_call_msg


def build(script):
    return create_agent(ScriptedChatModel(script=script), tools_mod.TOOLS,
                        system_prompt=agent_mod.SYSTEM_PROMPT)


def test_tool_call_then_answer_collects_tokens_steps_and_sources(monkeypatch):
    monkeypatch.setattr(tools_mod, "search_wikipedia", lambda q: (
        "Page: Haber process\nSummary: ...",
        [{"title": "Haber process", "url": "https://en.wikipedia.org/wiki/Haber_process"},
         {"title": "evil", "url": "https://evil.example/x"}]))
    ag = build([tool_call_msg("wikipedia", {"query": "Haber process"}, tokens=120),
                answer_msg("It makes ammonia.", tokens=60)])
    res = agent_mod.run_agent("What is the Haber process?", agent=ag)
    assert res.answer == "It makes ammonia."
    assert res.tools_used == ["wikipedia"]
    assert res.tokens == 180
    assert any("wikipedia" in s for s in res.steps)
    assert res.sources == [{"title": "Haber process", "url": "https://en.wikipedia.org/wiki/Haber_process"}]


def test_calculator_runs_through_the_graph():
    ag = build([tool_call_msg("calculate", {"expression": "2**10"}), answer_msg("1024")])
    res = agent_mod.run_agent("2^10?", agent=ag)
    assert res.tools_used == ["calculate"] and res.sources == [] and res.answer == "1024"


def test_malicious_calculator_input_is_neutralised(tmp_path):
    marker = tmp_path / "pwned"
    expr = f"__import__('pathlib').Path(r'{marker}').touch()"
    ag = build([tool_call_msg("calculate", {"expression": expr}), answer_msg("refused")])
    agent_mod.run_agent("run this", agent=ag)
    assert not marker.exists()


def test_no_tool_question():
    res = agent_mod.run_agent("hi", agent=build([answer_msg("Hello!")]))
    assert res.answer == "Hello!" and res.tools_used == [] and res.sources == []


def test_recursion_limit_stops_endless_tool_loops():
    ag = build([tool_call_msg("calculate", {"expression": "1+1"})])  # repeats forever
    with pytest.raises(GraphRecursionError):
        agent_mod.run_agent("loop", agent=ag)


def test_history_is_truncated_and_model_checked():
    long_history = [("user", f"q{i}") if i % 2 == 0 else ("assistant", f"a{i}") for i in range(20)]
    seen = {}

    class Spy:
        def stream(self, payload, config=None):
            seen["n"] = len(payload["messages"])
            seen["config"] = config
            yield {"model": {"messages": [answer_msg("ok")]}}

    agent_mod.run_agent("now", history=long_history, agent=Spy())
    assert seen["n"] == agent_mod.HISTORY_MESSAGES + 1
    assert seen["config"]["recursion_limit"] == agent_mod.RECURSION_LIMIT
    with pytest.raises(ValueError):
        agent_mod.run_agent("x", model="gpt-3.5-turbo", agent=Spy())
