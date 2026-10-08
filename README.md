# 🔬 Scientific Research Agent

A ReAct-style research assistant built with LangChain, LangGraph and Streamlit. Given a scientific question, the agent decides whether to search Wikipedia, ArXiv or PubMed, or to run a calculation, and answers with the sources it used.

[![tests](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml/badge.svg)](https://github.com/slastrzelec/17_research-agent-langchain/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangChain](https://img.shields.io/badge/LangChain-1.2-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-red)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Live demo:** https://research-agent-langchain.streamlit.app/ (free tier: the app sleeps after inactivity — click "wake up" and wait a minute).

## Features

- **4 tools**: Wikipedia, ArXiv, PubMed (NCBI E-utilities), calculator
- **ReAct agent** (`langgraph.prebuilt.create_react_agent`); the visible steps show which tool was called
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
agent.py        agent + tools (LangFuse optional)
app.py          Streamlit UI
safe_calc.py    safe arithmetic evaluator
pubmed.py       PubMed client (timeouts, defensive parsing)
limits.py       session and daily usage limits
database.py     SQLite storage, migration, retention
utils.py        HTML escaping, CSV export
tests/          pytest suite (no network, no API key needed)
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
pip install pytest && pytest      # tests
```

## Limitations

- Answer quality is **not evaluated**: there is no benchmark of tool choice or answer correctness, and the model can still hallucinate. Treat answers as a starting point and check the sources.
- Wikipedia and ArXiv results are truncated by the LangChain wrappers; PubMed returns at most 3 abstracts (3000 characters).
- The SQLite file lives on the app's local disk; on Streamlit Community Cloud it is lost on restart.
- The tests mock the network and the LLM; the live OpenAI and LangFuse paths are verified by hand only.

## Example questions

- `What are the medical applications of carbon nanotubes?`
- `Find recent papers on CRISPR gene editing`
- `Convert 2.5 nanometers to meters`
- `What is the difference between SWCNT and MWCNT?`

## License

MIT — see [LICENSE](LICENSE).
