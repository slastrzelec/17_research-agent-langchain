import pytest

from limits import (
    MAX_QUESTION_CHARS,
    MAX_QUESTIONS_PER_SESSION,
    MAX_TOKENS_PER_SESSION,
    LimitExceeded,
    SessionUsage,
    UsageLimiter,
    cost_weight,
)


def test_question_validation():
    s = SessionUsage()
    s.check("What is a CNT?", "gpt-4o-mini")
    for bad in ["", "   ", "x" * (MAX_QUESTION_CHARS + 1)]:
        with pytest.raises(LimitExceeded):
            s.check(bad, "gpt-4o-mini")


def test_model_allow_list_and_weights():
    assert cost_weight("gpt-4o") == 15 * cost_weight("gpt-4o-mini")
    with pytest.raises(LimitExceeded):
        cost_weight("gpt-3.5-turbo")
    with pytest.raises(LimitExceeded):
        SessionUsage().check("hi", "o3-pro")


def test_session_question_cap():
    s = SessionUsage()
    for _ in range(MAX_QUESTIONS_PER_SESSION):
        s.check("q", "gpt-4o-mini")
        s.record("gpt-4o-mini", 10)
    with pytest.raises(LimitExceeded):
        s.check("q", "gpt-4o-mini")


def test_session_token_cap_weighted():
    s = SessionUsage()
    assert s.record("gpt-4o", 1000) == 15000
    s.record("gpt-4o-mini", MAX_TOKENS_PER_SESSION)
    with pytest.raises(LimitExceeded):
        s.check("q", "gpt-4o-mini")


def test_global_daily_budget_and_rollover():
    day = ["2026-10-08"]
    lim = UsageLimiter(daily_budget=100, today=lambda: day[0])
    lim.check()
    lim.add(100)
    with pytest.raises(LimitExceeded):
        lim.check()
    day[0] = "2026-10-09"
    lim.check()
    assert lim.used_today == 0


def test_negative_tokens_do_not_reduce_usage():
    lim = UsageLimiter(daily_budget=100)
    lim.add(50)
    lim.add(-1000)
    assert lim.used_today == 50
