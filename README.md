# 🔬 Scientific Research Agent

An AI-powered research assistant built with LangChain, LangGraph, and Streamlit. The agent autonomously selects the best tool to answer scientific questions — searching Wikipedia, ArXiv, PubMed, or performing calculations.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangChain](https://img.shields.io/badge/LangChain-1.2-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-red)
![LangFuse](https://img.shields.io/badge/LangFuse-3.14-purple)

## 🚀 Features

- **4 tools**: Wikipedia, ArXiv, PubMed, Calculator
- **ReAct agent loop** — autonomous reasoning and tool selection
- **Conversation memory** — agent remembers context within a session
- **SQLite logging** — every query is saved with tokens used and tools called
- **LangFuse observability** — full trace monitoring, latency, and cost tracking
- **Export to CSV** — download full conversation history
- **GPT model selector** — switch between gpt-4o-mini, gpt-3.5-turbo, gpt-4o

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Agent framework | LangChain + LangGraph |
| LLM | OpenAI GPT-4o-mini |
| Tools | Wikipedia, ArXiv, PubMed, Calculator |
| UI | Streamlit |
| Database | SQLite |
| Observability | LangFuse |
| Environment | Python 3.11, Conda |

## 📁 Project Structure

```
research-agent/
├── agent.py          # Agent logic, tools, LangFuse integration
├── app.py            # Streamlit UI
├── database.py       # SQLite logging
├── notebooks/
│   └── 01_agent_dev.ipynb  # Development notebook
├── requirements.txt
├── .env              # API keys (not committed)
├── .gitignore
└── README.md
```

## ⚙️ Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/research-agent.git
cd research-agent
```

2. Create and activate conda environment
```bash
conda create -n research-agent python=3.11 -y
conda activate research-agent
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Create `.env` file
```
OPENAI_API_KEY=sk-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

5. Run the app
```bash
streamlit run app.py
```

## 🧠 How It Works

The agent uses the **ReAct (Reasoning + Acting)** pattern:

```
User Question
     ↓
LLM decides which tool to use
     ↓
Tool is called (Wikipedia / ArXiv / PubMed / Calculator)
     ↓
LLM observes the result
     ↓
Final Answer
```

Every step is traced in LangFuse for full observability.

## 📊 Example Queries

- `What are the medical applications of carbon nanotubes?` → PubMed + Wikipedia
- `Find recent papers on CRISPR gene editing` → ArXiv
- `Convert 2.5 nanometers to meters` → Calculator
- `What is the difference between SWCNT and MWCNT?` → Wikipedia
