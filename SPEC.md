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

---

# Release 2 — evaluation, sources, modern stack

Status: approved for implementation 2026-10-08. Builds on sections 1–8 (all their security rules stay in force).

## 9. Goals
1. **Measure** the agent instead of asserting it works: tool choice, calculator correctness, safety behaviour, source coverage, cost.
2. **Show sources**: every answer lists the pages/papers the tools actually retrieved, as links.
3. Leave deprecated APIs behind (`create_react_agent` → `langchain.agents.create_agent`) and add lint + dependency hygiene to CI.
4. Small robustness gains: model timeout/retries, hard timeouts on every external HTTP call.

## 10. Evaluation design
**Cases** — `evaluation/cases.jsonl`, 32 hand-written cases, 16 `dev` + 16 `test`, same category mix in both:
Wikipedia 4, ArXiv 3, PubMed 3, calculator 3, no-tool 1, safety 2 (calculator code-injection, system-prompt extraction).
Fields: `id, split, category, question, expected_tools_any, allow_no_tool, numeric_answer, must_not_match`.

**Metrics** (each with a Wilson 95 % interval — n is small, so intervals are wide and are reported, not hidden):
| Metric | Definition |
|---|---|
| tool_ok | called ∩ expected ≠ ∅ (or no tool call when `allow_no_tool`; no-tool cases: no call at all) |
| numeric_ok | some number in the answer equals `numeric_answer` within 1 % (handles `1.5e-9`, `1.5 × 10^-9`, `1,234.5`) |
| safety_ok | answer does not match any `must_not_match` pattern and no code was executed |
| sources_ok | retrieval cases: at least one source returned by the tools |
| error rate, mean tokens, median latency | from the run |
Not measured (stated in the README): factual correctness of free-text answers. No LLM-as-judge (cost, self-preference bias). Instead the owner grades a sample of 8 test answers by hand (0/1/2) in `evaluation/manual_review.md`.

**Leakage / overfitting rules** (same discipline as the owner's other projects):
- Prompt or tool changes may be tuned **on `dev` only**. `test` is run once per (model, prompt-hash); the runner keeps `evaluation/results/test_runs.json` and refuses a second `test` run for the same pair unless `--force-rerun-test` is given, which is then recorded in that log.
- Case text is never embedded in the system prompt, tool descriptions or tests of app behaviour; a unit test fails if any case question appears in `agent.py`, `tools.py` or `SYSTEM_PROMPT`.
- Each result file stores: model, prompt hash, split, per-case outcome, summary. Nothing else.

**Data security of the eval**: cases are synthetic (no personal data, no real patient or customer text). Questions and answers go to OpenAI like any demo query. The runner reads `OPENAI_API_KEY` from the environment only, never prints or stores it, and has a hard `--max-tokens` guard (default 400 000). Results contain no secrets and may be committed.

**Execution**: scoring logic is pure Python and unit-tested with fake run results (no API). The live run (`python -m evaluation.run_eval --split dev|test`) is done by the owner with his own key; the README shows real numbers only after that run. Until then it says "not yet run".

## 11. Sources
- Tools return `(text, sources)` using LangChain's `content_and_artifact`; sources are `{title, url}` produced by our code from API responses — **not parsed from model text or tool prose**, so prompt injection cannot add links.
- Only `https` URLs on `en.wikipedia.org`, `arxiv.org`, `pubmed.ncbi.nlm.nih.gov` are accepted (`sources.clean_sources`); rendering escapes titles and URLs.
- UI label: "Sources retrieved by the tools" — retrieved is not the same as cited in the answer, and the README says so.
- Wikipedia and ArXiv move from `langchain-community` wrappers to our own thin clients on `requests` (timeout 10 s, defensive parsing, `defusedxml` for the Atom feed). Dependencies `langchain-community`, `wikipedia`, `arxiv` are dropped from `requirements.txt`; the dev notebook states what it needs.
- PubMed: add `esummary` for titles; PMID validated as digits before building a URL.

## 12. Modern stack and CI
- `agent.py`: `langchain.agents.create_agent`, `run_agent` returns an `AgentResult` dataclass (answer, steps, tools_used, tokens, sources). Stream node names handled for the new graph.
- Model client: `timeout=30`, `max_retries=2`.
- `pyproject.toml`: ruff (E, F, I, B, UP, S; tests may use `assert`) and pytest settings. CI runs ruff, then pytest; a separate non-blocking `pip-audit` job; Dependabot for pip and GitHub Actions (weekly).
- A scripted fake chat model drives an integration test of `run_agent` (tool call → tool result → answer, usage tokens, sources, recursion limit) without network.

## 13. Acceptance criteria (release 2)
- Ruff clean; all tests green locally; CI green after push (owner verifies).
- `run_agent` integration test passes with the fake model; sources survive end-to-end into the UI test.
- Scoring tests cover number extraction, Wilson interval, test-split guard, leakage check.
- Stated as unverified until the owner runs it: real eval numbers, behaviour of the live OpenAI model with the new prompt.

## 14. Change log (continued)
- 2026-10-08 — release 2 spec: evaluation harness, sources, create_agent migration, lint/audit.
- 2026-10-08 — release 2 implemented: `create_agent` + `AgentResult`; own Wikipedia/ArXiv/PubMed clients with sources (content_and_artifact); `evaluation/` (32 cases, scoring, guarded runner); ruff, pip-audit, Dependabot. Dependencies bumped to versions without known advisories (pip-audit found 12 advisories in the old pins: langchain, langchain-core, langchain-openai, requests, langgraph-sdk); 91 tests pass on the new pins. Unverified: live OpenAI/Wikipedia/ArXiv/PubMed calls; evaluation numbers (owner runs `evaluation.run_eval`). Spec deviation: tests also assert that the repo's own `.env` can never enable tracing in tests (conftest blanks LangFuse keys).

## 15. Answer rendering (addendum, 2026-10-08)
Problem seen on the live demo: models answer in Markdown/LaTeX (`\[ ... \]`), but answers were shown as escaped plain text, so formulas appeared as raw LaTeX.
- Answers are rendered with `st.markdown` **without** `unsafe_allow_html`, so raw HTML from the model is never interpreted.
- LaTeX delimiters `\( \)` / `\[ \]` are converted to the `$ … $` / `$$ … $$` that Streamlit renders; literal `$` signs are escaped first so prices are not read as math.
- **Markdown images are stripped** from model output before rendering. Reason: an auto-loaded image URL is a known data-exfiltration channel for prompt-injected answers (the URL can carry conversation text to a third-party server without any click). Links stay as text and need a user click.
- Tests: LaTeX conversion, `$` escaping, image stripping (inline and reference style), and that the answer element is created with `allow_html == False`.
