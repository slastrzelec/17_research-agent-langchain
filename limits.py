"""Usage limits that protect the owner's OpenAI budget on a public demo."""
import threading
from datetime import datetime, timezone

MAX_QUESTION_CHARS = 1000
MAX_QUESTIONS_PER_SESSION = 15
MAX_TOKENS_PER_SESSION = 80_000      # weighted
MAX_TOKENS_PER_DAY = 1_500_000       # weighted, whole app
MODEL_WEIGHTS = {"gpt-4o-mini": 1, "gpt-4o": 15}
ALLOWED_MODELS = list(MODEL_WEIGHTS)


class LimitExceeded(Exception):
    """Raised when a request would break a usage limit; message is user-facing."""


def cost_weight(model: str) -> int:
    if model not in MODEL_WEIGHTS:
        raise LimitExceeded(f"Model not allowed: {model}")
    return MODEL_WEIGHTS[model]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class UsageLimiter:
    """Process-wide daily budget (thread-safe). Session counters live in SessionUsage."""

    def __init__(self, daily_budget: int = MAX_TOKENS_PER_DAY, today=_today):
        self.daily_budget = daily_budget
        self._today = today
        self._day = today()
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self):
        day = self._today()
        if day != self._day:
            self._day, self._used = day, 0

    def check(self):
        with self._lock:
            self._roll()
            if self._used >= self.daily_budget:
                raise LimitExceeded("The demo's daily budget is used up. Please try again tomorrow.")

    def add(self, weighted_tokens: int):
        with self._lock:
            self._roll()
            self._used += max(0, int(weighted_tokens))

    @property
    def used_today(self) -> int:
        with self._lock:
            self._roll()
            return self._used


class SessionUsage:
    """Per-visitor counters, kept in st.session_state."""

    def __init__(self):
        self.questions = 0
        self.weighted_tokens = 0

    def check(self, question: str, model: str):
        cost_weight(model)
        if not question or not question.strip():
            raise LimitExceeded("Please enter a question.")
        if len(question) > MAX_QUESTION_CHARS:
            raise LimitExceeded(f"Question is too long (max {MAX_QUESTION_CHARS} characters).")
        if self.questions >= MAX_QUESTIONS_PER_SESSION:
            raise LimitExceeded(f"Session limit reached ({MAX_QUESTIONS_PER_SESSION} questions). Reload the page to start a new session.")
        if self.weighted_tokens >= MAX_TOKENS_PER_SESSION:
            raise LimitExceeded("Session token budget used up. Reload the page to start a new session.")

    def record(self, model: str, tokens: int) -> int:
        weighted = max(0, int(tokens)) * cost_weight(model)
        self.questions += 1
        self.weighted_tokens += weighted
        return weighted
