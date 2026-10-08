# 🔬 Scientific Research Agent

A ReAct-style research assistant built with LangChain, LangGraph and Streamlit. Given a scientific question, the agent decides whether to search Wikipedia, ArXiv or PubMed, or to run a calculation, and answers with the sources it used.

[![tests](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml/badge.svg)](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangChain](https://img.shields.io/badge/LangChain-1.3-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-red)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Live demo:** https://research-agent-langchain.streamlit.app/ (free tier: the app sleeps after inactivity — click "wake up" and wait a minute).  
**Portfolio page:** [slastrzelec.github.io/portfolio/17_research-agent-langchain](https://slastrzelec.github.io/portfolio/17_research-agent-langchain/) · **Spec and threat model:** [SPEC.md](SPEC.md)

## Features

- **4 tools**: Wikipedia, ArXiv, PubMed (thin `requests` clients with timeouts), calculator
- **Tool-calling agent** (`langchain.agents.create_agent`, ReAct loop); the visible steps show which tool was called
- **Sources**: links to the pages and papers the tools actually retrieved, shown under every answer (taken from the API responses, not from model text; allow-listed hosts only). "Retrieved" does not guarantee the answer cites them.
- **Short-term memory**: the last 6 messages of the session are sent back to the model
- **Per-session history**: queries are logged to SQLite, shown and exported (CSV) only for your own session
- **Optional LangFuse tracing**: enabled only if both LangFuse keys are set
- **Model selector**: `gpt-4o-mini` (default) or `gpt-4o`

## Safety and cost controls

The app is meant to run publicly on the owner's OpenAI key, so it is hardened (see [SPEC.md](SPEC.md) for the threat model):

- the calculator uses an AST whitelist (`safe_calc.py`), **not** `eval()`;
- all user and model text is HTML-escaped before rendering; exported CSV is protected against formula injection;
- limits: 1000 characters per question, 15 questions and 80 000 weighted tokens per session, a daily token budget for the whole app, `recursion_limit=12` for the agent; `gpt-4o` counts 15× more than `gpt-4o-mini`;
- tools have timeouts and fail with a short message instead of crashing the agent;
- data: questions go to OpenAI (and LangFuse if configured), are stored in a local SQLite file for 30 days and are visible only to the session that wrote them. Don't type personal data into the demo.

Not covered: authentication and per-IP rate limiting. The daily budget and an OpenAI-side spending limit are the backstops.

## Project structure

```
agent.py        agent graph, run_agent() -> AgentResult (LangFuse optional)
tools.py        the four LangChain tools (content + sources)
wiki.py         Wikipedia client
arxiv_search.py ArXiv client
app.py          Streamlit UI
safe_calc.py    safe arithmetic evaluator
pubmed.py       PubMed client
sources.py      source-link allow-list
evaluation/     eval cases (dev/test), scoring, runner
limits.py       session and daily usage limits
database.py     SQLite storage, migration, retention
utils.py        HTML escaping, CSV export
tests/          pytest suite (no network, no API key; a scripted fake model drives the real agent graph)
pyproject.toml  ruff + pytest config
SPEC.md         specification and threat model
notebooks/      01_agent_dev.ipynb — early development notebook
```

## Run locally

```bash
git clone https://github.com/slastrzelec/17_research-agent-langchain.git
cd 17_research-agent-langchain
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` (never commit it):

```
OPENAI_API_KEY=sk-...
# optional tracing
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

```bash
streamlit run app.py
pip install -r requirements-dev.txt
ruff check . && pytest            # lint + tests
```

## Testing

**95 automated tests** (pytest, in [`tests/`](tests/)) run on every push in [GitHub Actions](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml) (config: [ci.yml](.github/workflows/ci.yml)) together with a `ruff` lint check; a separate job runs `pip-audit` on the pinned dependencies. The suite needs **no API key and no network**, so anyone can run it in seconds: `pytest`.

| Area | What is verified |
|---|---|
| Calculator security | valid arithmetic, and rejection of code injection (`__import__`, `open`, attribute access, lambdas), huge exponents, over-long or too complex input; a test proves a malicious expression does not touch the file system |
| Agent graph | the real LangGraph agent is driven by a scripted fake model: tool call → tool result → answer, token counting, source collection, recursion limit stops endless tool loops, history truncation, model allow-list |
| Search clients | Wikipedia, ArXiv and PubMed parsers with mocked HTTP: success, empty results, HTTP errors, malformed JSON/XML, timeouts, XML-bomb input; they never raise into the agent |
| Sources | only `https` links on allow-listed hosts survive; grouping and overflow handling |
| Limits and cost | per-session and daily budgets, model weights, day rollover |
| Data handling | SQLite: sessions are isolated, SQL-injection strings stay inert, old schema is migrated, 30-day retention purge |
| UI (Streamlit `AppTest`) | HTML in a question is escaped, answers are rendered without raw HTML, too-long questions never reach the agent, errors show only the error type while the traceback goes to the server log, one visitor never sees another's history |
| Output safety | CSV export is protected against spreadsheet formula injection; Markdown images are stripped from model output; LaTeX is converted for rendering |
| Evaluation code | number extraction (`1.5e-9`, `1.5 × 10^-9`), Wilson intervals, the rule that the `test` split runs once per configuration, and a leakage check that no evaluation question appears in the prompt, tools or app code |

I checked that the tests can fail: breaking HTML escaping or the calculator whitelist turns the relevant tests red.

**What the tests do not cover:** real calls to OpenAI, Wikipedia, ArXiv, PubMed and LangFuse (the suite mocks them), and the quality of free-text answers. Those are checked by hand on the live demo, and answer quality by the evaluation harness below.

## Evaluation

[`evaluation/`](evaluation/) holds 32 hand-written cases ([`cases.jsonl`](evaluation/cases.jsonl), runner [`run_eval.py`](evaluation/run_eval.py), raw [results](evaluation/results/)) (16 `dev`, 16 `test`: Wikipedia, ArXiv, PubMed, calculator, no-tool and two safety categories). Metrics: tool choice, numeric correctness of calculator answers, safety checks (code injection, system-prompt extraction), source coverage, tokens and latency, each with a Wilson 95 % interval. Rules: tune on `dev` only; `test` runs once per model + prompt/tool configuration (the runner refuses a repeat). Free-text factual correctness is **not** measured automatically — see [`evaluation/manual_review.md`](evaluation/manual_review.md).

```bash
python -m evaluation.run_eval --split dev      # needs OPENAI_API_KEY, costs a few cents
```

**Results** (config `ce2c3dbfa5d7` = system prompt + tool descriptions; model `gpt-4o-mini`; 95 % Wilson intervals):

| split | tool choice | calculator | safety | sources | mean tokens / question | median latency |
|---|---|---|---|---|---|---|
| dev (16 cases) | 14/14 (CI 0.79–1.00) | 3/3 (0.44–1.00) | 2/2 (0.34–1.00) | 10/10 (0.72–1.00) | 1 027 | 5.5 s |
| test (16 cases) | not run yet | not run yet | not run yet | not run yet | – | – |

How to read this honestly: perfect scores on 16 easy cases mean the agent handles the *obvious* cases, not that it is 100 % reliable — the intervals are wide and the suite has little power to separate good from very good. "Tool choice" counts a case as correct if the expected tool was called, so extra calls (2 of 14 retrieval cases also called a second search tool) are not penalised. The code-injection safety case was refused by the model before the calculator was reached; the calculator's own defences are covered by unit tests, not by this metric. Free-text factual correctness is not measured automatically.

## Limitations

- Answer quality is only partly measured: the evaluation covers tool choice, calculator correctness, safety and source coverage on 32 cases, **not** the factual correctness of free-text answers, and the model can still hallucinate. Treat answers as a starting point and check the sources.
- Search results are truncated: Wikipedia 2 intros (1500 characters each), ArXiv 3 abstracts, PubMed 3 abstracts (3000 characters in total).
- The SQLite file lives on the app's local disk; on Streamlit Community Cloud it is lost on restart.
- The tests mock the network and the LLM; the live OpenAI, Wikipedia, ArXiv, PubMed and LangFuse paths are verified by hand only.
- Dependencies were upgraded to versions without known advisories (`pip-audit` clean at the time of writing); CI repeats the check on every push (informational job) and Dependabot proposes updates weekly.

## Example questions

- `What are the medical applications of carbon nanotubes?`
- `Find recent papers on CRISPR gene editing`
- `Convert 2.5 nanometers to meters`
- `What is the difference between SWCNT and MWCNT?`

## License

MIT — see [LICENSE](LICENSE).
