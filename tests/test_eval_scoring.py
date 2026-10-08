import json
import pathlib

import pytest

from evaluation import run_eval
from evaluation.scoring import (
    check_test_rerun,
    extract_numbers,
    leakage_check,
    load_cases,
    numeric_ok,
    record_test_run,
    safety_ok,
    score_case,
    sources_ok,
    summarize,
    tool_ok,
    wilson,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = load_cases(ROOT / "evaluation" / "cases.jsonl")


def case(**kw):
    base = dict(id="x", split="dev", category="c", question="q", expected_tools_any=["calculate"],
                allow_no_tool=False, numeric_answer=None, must_not_match=[])
    return {**base, **kw}


# --- the case file itself -----------------------------------------------------------------
def test_case_file_shape():
    assert len(CASES) == 32
    assert {c["split"] for c in CASES} == {"dev", "test"}
    for split in ("dev", "test"):
        cats = sorted(c["category"] for c in CASES if c["split"] == split)
        assert len(cats) == 16
    cat_mix = lambda s: sorted(c["category"] for c in CASES if c["split"] == s)  # noqa: E731
    assert cat_mix("dev") == cat_mix("test")
    assert len({c["question"] for c in CASES}) == 32


def test_no_case_question_leaks_into_prompt_tools_or_app_code():
    import agent
    texts = {"SYSTEM_PROMPT": agent.SYSTEM_PROMPT}
    for name in ("agent.py", "tools.py", "app.py", "wiki.py", "arxiv_search.py", "pubmed.py"):
        texts[name] = (ROOT / name).read_text(encoding="utf-8")
    for t in agent.TOOLS:
        texts[f"tool:{t.name}"] = t.description
    assert leakage_check(CASES, texts) == []


def test_leakage_check_detects_a_leak():
    hits = leakage_check([case(id="a", question="What is X?")], {"p": "...  what   is x? ..."})
    assert hits == [("a", "p")]


# --- numbers --------------------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("4.2e-9 m", 4.2e-9), ("4.2 × 10^-9 meters", 4.2e-9), ("4.2 x 10⁻⁹ m", 4.2e-9),
    ("= 4.2*10^{-9}", 4.2e-9), ("0.0000000042", 4.2e-9), ("1,048.576", 1048.576),
    ("about 408.", 408), ("−", None),
])
def test_extract_numbers(text, expected):
    nums = extract_numbers(text)
    if expected is None:
        assert nums == []
    else:
        assert any(abs(n - expected) <= 1e-9 * abs(expected) + 1e-30 for n in nums), nums


def test_numeric_ok_tolerance():
    assert numeric_ok("E ≈ 3.98 × 10^-19 J", 3.9756e-19)       # 3 sig. figs. rounding
    assert not numeric_ok("E ≈ 3.5 × 10^-19 J", 3.9756e-19)
    assert numeric_ok("26.85 °C", 26.85) and not numeric_ok("27.85 °C", 26.85)
    assert not numeric_ok("no numbers here", 5)


# --- per-case rules ---------------------------------------------------------------------------
def test_tool_ok_rules():
    assert tool_ok(case(), ["calculate"]) and not tool_ok(case(), [])
    assert not tool_ok(case(), ["wikipedia"])
    assert tool_ok(case(allow_no_tool=True), [])
    assert not tool_ok(case(allow_no_tool=True), ["wikipedia"])
    assert tool_ok(case(expected_tools_any=[]), []) and not tool_ok(case(expected_tools_any=[]), ["arxiv"])
    assert tool_ok(case(expected_tools_any=None), ["anything"]) is None


def test_safety_and_sources():
    c = case(must_not_match=[r"root:x:0", r"app\.py"])
    assert safety_ok(c, "I cannot do that.") and not safety_ok(c, "root:x:0:0:root")
    assert not safety_ok(c, "files: APP.PY")
    assert safety_ok(case(), "x") is None
    assert sources_ok(case(), ["calculate"], []) is None
    assert sources_ok(case(), ["arxiv"], [{"url": "u"}]) is True
    assert sources_ok(case(), ["arxiv"], []) is False


def test_score_case_and_errors():
    ok = score_case(case(numeric_answer=4.0), {"answer": "4", "tools_used": ["calculate"], "sources": [],
                                              "tokens": 10, "latency_s": 1.0, "error": None})
    assert ok["tool_ok"] and ok["numeric_ok"] and ok["safety_ok"] is None
    bad = score_case(case(numeric_answer=4.0), {"error": "Timeout"})
    assert bad["tool_ok"] is False and bad["numeric_ok"] is False and bad["error"] == "Timeout"


def test_wilson_and_summary():
    lo, hi = wilson(8, 16)
    assert 0.27 < lo < 0.29 and 0.71 < hi < 0.73
    assert wilson(0, 0) == (0.0, 0.0) and wilson(16, 16)[1] == 1.0
    scored = [score_case(case(), {"answer": "", "tools_used": ["calculate"], "tokens": 100, "latency_s": 2}),
              score_case(case(), {"answer": "", "tools_used": [], "tokens": 50, "latency_s": 4}),
              score_case(case(), {"error": "X"})]
    s = summarize(scored)
    assert s["tool_ok"]["k"] == 1 and s["tool_ok"]["n"] == 3 and s["errors"] == 1
    assert s["mean_tokens"] == 50.0 and s["numeric_ok"]["n"] == 0 and s["numeric_ok"]["rate"] is None


# --- test-split discipline --------------------------------------------------------------------
def test_test_split_guard(tmp_path):
    log = tmp_path / "test_runs.json"
    check_test_rerun(log, "m", "h", "test", False)                  # first time: fine
    record_test_run(log, "m", "h", False, "r.json")
    with pytest.raises(RuntimeError):
        check_test_rerun(log, "m", "h", "test", False)              # second time: refused
    check_test_rerun(log, "m", "h2", "test", False)                 # changed prompt/tools: allowed
    check_test_rerun(log, "other", "h", "test", False)              # other model: allowed
    check_test_rerun(log, "m", "h", "test", True)                   # forced
    check_test_rerun(log, "m", "h", "dev", False)                   # dev is never restricted


# --- runner end to end with a fake agent --------------------------------------------------------
def test_run_eval_end_to_end(tmp_path, monkeypatch, capsys):
    import agent

    class R:
        def __init__(self, q):
            self.answer, self.tools_used, self.sources, self.tokens = f"re: {q}", ["calculate"], [], 1000

    monkeypatch.setattr(agent, "run_agent", lambda q, h, model: R(q))
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    monkeypatch.setattr(run_eval, "TEST_LOG", tmp_path / "test_runs.json")
    assert run_eval.main(["--split", "test"]) == 0
    files = [p for p in tmp_path.glob("*_test_*.json")]
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["split"] == "test" and len(data["cases"]) == 16 and data["prompt_hash"] == agent.PROMPT_HASH
    assert "sk-" not in files[0].read_text(encoding="utf-8")
    with pytest.raises(RuntimeError):
        run_eval.main(["--split", "test"])                           # second test run is refused
    assert run_eval.main(["--split", "test", "--force-rerun-test"]) == 0


def test_run_eval_token_budget_and_errors(tmp_path, monkeypatch):
    import agent

    def boom(q, h, model):
        raise RuntimeError("secret-ish detail")

    monkeypatch.setattr(agent, "run_agent", boom)
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    monkeypatch.setattr(run_eval, "TEST_LOG", tmp_path / "t.json")
    assert run_eval.main(["--split", "dev"]) == 0
    data = json.loads(next(tmp_path.glob("*_dev_*.json")).read_text(encoding="utf-8"))
    assert all(c["error"] == "RuntimeError" for c in data["cases"])      # type only, no message
    assert data["summary"]["errors"] == 16
