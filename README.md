# 🔬 Scientific Research Agent

A ReAct-style research assistant built with LangChain, LangGraph and Streamlit. Given a scientific question, the agent decides whether to search Wikipedia, ArXiv or PubMed, or to run a calculation, and answers with the sources it used.

[![tests](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml/badge.svg)](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangChain](https://img.shields.io/badge/LangChain-1.2-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-red)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Live demo:** https://research-agent-langchain.streamlit.app/ (free tier: the app sleeps after inactivity — click "wake up" and wait a minute).

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

## Evaluation

`evaluation/` holds 32 hand-written cases (16 `dev`, 16 `test`: Wikipedia, ArXiv, PubMed, calculator, no-tool and two safety categories). Metrics: tool choice, numeric correctness of calculator answers, safety checks (code injection, system-prompt extraction), source coverage, tokens and latency, each with a Wilson 95 % interval. Rules: tune on `dev` only; `test` runs once per model + prompt/tool configuration (the runner refuses a repeat). Free-text factual correctness is **not** measured automatically — see `evaluation/manual_review.md`.

```bash
python -m evaluation.run_eval --split dev      # needs OPENAI_API_KEY, costs a few cents
```

**Results: not yet run.** (This table is filled in only from real runs.)

| split | model | tool choice | calculator | safety | sources | mean tokens |
|---|---|---|---|---|---|---|
| dev | gpt-4o-mini | – | – | – | – | – |
| test | gpt-4o-mini | – | – | – | – | – |

## Limitations

- Answer quality is **not evaluated**: there is no benchmark of tool choice or answer correctness, and the model can still hallucinate. Treat answers as a starting point and check the sources.
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
