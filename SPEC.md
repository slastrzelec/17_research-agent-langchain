# SPEC — Scientific Research Agent (hardening release)

Status: approved for implementation 2026-10-08. Scope: fix the security, cost, privacy and
correctness problems found in the audit; add tests and CI. No new product features.

## 1. Goals
1. A public demo cannot execute arbitrary code, inject HTML/JS, or run up an unbounded OpenAI bill.
2. One visitor never sees another visitor's questions or answers.
3. Every tool fails gracefully (timeouts, bad responses) instead of crashing the agent.
4. The behaviour is covered by tests that run without an OpenAI key and without network access.
5. Documentation says only what the code does.

## 2. Threat model (what we defend against)
| Threat | Source | Mitigation |
|---|---|---|
| Arbitrary code execution | `eval()` on model-written input (prompt injection via user text or tool output) | `safe_calc.py`: AST whitelist (numbers, + - * / // % **, unary +/-, a few math functions); no names, attributes, calls to anything else; length, exponent and size caps |
| HTML/JS injection | user question and model answer rendered with `unsafe_allow_html=True` | `html.escape` on every dynamic value before it goes into HTML; static CSS only |
| Cost abuse | public app on the owner's OpenAI key | per-question length cap, per-session question cap, per-session and global (process-wide, per-day) weighted token budgets, `recursion_limit`, history truncated to the last turns, expensive model weighted higher |
| Data exposure between visitors | one shared SQLite table, global statistics and CSV export | each browser session gets a random `session_id`; every read (stats, recent queries, CSV) is filtered by it |
| Long-term storage of user text | permanent logging | rows older than 30 days are purged at start-up; UI states that questions are stored and sent to OpenAI (and LangFuse if configured) |
| CSV/formula injection | model/user text in exported CSV opened in Excel | cells starting with `= + - @` or tab/CR are prefixed with `'` |
| Prompt injection via tool results | Wikipedia / ArXiv / PubMed text | agent has no side-effecting tools (read-only search + safe calculator); system prompt tells the model to treat tool output as data; answers are only displayed, never executed |
| Secret leakage | `.env`, notebook outputs | `.env` stays git-ignored; notebook outputs must not contain key material; no secret is ever written to the DB, logs or UI |
| Dependency drift | unpinned installs | versions stay pinned in `requirements.txt` |

Out of scope (stated honestly): authentication, rate limiting per IP (Streamlit Community Cloud
gives no stable client IP), protection against a determined attacker opening many sessions —
the **global daily budget** is the backstop for that, and an OpenAI-side monthly spend limit is
the final one.

## 3. Data handling
- Sent to third parties: question + conversation tail → OpenAI; traces → LangFuse **only if**
  `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set (otherwise tracing is off).
- Stored locally: SQLite (`research_agent.db`, git-ignored), columns
  `id, timestamp, question, answer, tools_used, tokens_used, session_id`. Old schema is migrated
  in place (`ALTER TABLE … ADD COLUMN session_id`); legacy rows have `session_id IS NULL` and are
  never shown. Retention: 30 days.
- Not stored: API keys, IP addresses, any user identifier other than the random session id.

## 4. Limits (defaults, constants in `limits.py`)
| Limit | Value |
|---|---|
| Question length | 1000 chars |
| Questions per session | 15 |
| Weighted tokens per session | 80 000 |
| Weighted tokens per UTC day, whole app | 1 500 000 |
| Model weights | gpt-4o-mini ×1, gpt-4o ×15 |
| Agent `recursion_limit` | 12 |
| History sent to model | last 6 messages |
| HTTP timeout (PubMed) | 10 s |
`gpt-3.5-turbo` is removed from the selector (deprecated).

## 5. Module design
- `safe_calc.py` — `safe_eval(expr) -> int | float`; raises `CalcError`.
- `pubmed.py` — `search_pubmed(query, http=requests) -> str`; timeout, status check, defensive JSON parsing, output truncated to 3000 chars.
- `limits.py` — `QuestionTooLong`/`LimitExceeded`, `UsageLimiter` (session + global, injectable clock), `cost_weight(model)`.
- `utils.py` — `esc`, `format_step`, `tool_icon`, `rows_to_csv` (formula-safe).
- `database.py` — context-managed connections, migration, `session_id` filtering, retention purge, `RESEARCH_AGENT_DB` env override for tests.
- `agent.py` — agent built once per model (cached); LangFuse optional; no mutable defaults; system prompt; `run_agent(...)` returns the same 4-tuple as before.
- `app.py` — settings rendered before use (fixes one-run lag in model selector), escaping, limits, friendly errors, per-session stats/export, privacy note.

## 6. Tests (pytest, no network, no API key)
safe_calc (valid maths, rejected names/attributes/calls/huge exponents/long input), pubmed
(mocked HTTP: success, empty, HTTP error, malformed JSON, timeout), limits (caps, global budget,
day rollover), database (isolation by session, migration of an old-schema DB, retention),
utils (escaping, CSV formula guard), app (Streamlit `AppTest` with a stubbed `agent`: HTML in a
question is shown escaped, limit message appears, only own session's rows are listed).
CI: GitHub Actions, Python 3.11, `pip install -r requirements.txt pytest`, `pytest`.

## 7. Acceptance criteria
- `grep -n "eval(" *.py` finds no call of the builtin; `unsafe_allow_html` is used only with escaped values.
- All tests green locally; CI green after push (verified by the owner).
- Not verified by tests and stated as such in the README: answer quality of the live agent, real OpenAI/LangFuse calls.

## 8. Change log
- 2026-10-08 — spec written after audit; implementation follows.
