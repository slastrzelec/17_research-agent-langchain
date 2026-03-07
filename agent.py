from dotenv import load_dotenv
import os
import requests
from langchain_openai import ChatOpenAI
from langchain_community.tools import WikipediaQueryRun, ArxivQueryRun
from langchain_community.utilities import WikipediaAPIWrapper, ArxivAPIWrapper
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from langfuse.langchain import CallbackHandler

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
arxiv_tool = ArxivQueryRun(api_wrapper=ArxivAPIWrapper())

@tool
def calculate(expression: str) -> str:
    """Useful for mathematical calculations. Input should be a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

@tool
def pubmed_search(query: str) -> str:
    """Search PubMed for biomedical research papers. Use for medical, clinical, or biological research questions."""
    try:
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": 3,
            "retmode": "json"
        }
        search_resp = requests.get(search_url, params=search_params)
        ids = search_resp.json()["esearchresult"]["idlist"]

        if not ids:
            return "No results found on PubMed."

        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "rettype": "abstract",
            "retmode": "text"
        }
        fetch_resp = requests.get(fetch_url, params=fetch_params)
        return fetch_resp.text[:3000]

    except Exception as e:
        return f"PubMed error: {e}"

tools = [wiki_tool, arxiv_tool, pubmed_search, calculate]

def run_agent(question: str, history: list = [], model: str = "gpt-4o-mini"):
    llm = ChatOpenAI(model=model, temperature=0)
    agent_executor = create_react_agent(llm, tools)

    # Langfuse handler
    langfuse_handler = CallbackHandler()

    messages = history + [("user", question)]
    steps = []
    final_answer = ""
    tools_used = []
    total_tokens = 0

    for chunk in agent_executor.stream(
        {"messages": messages},
        config={"callbacks": [langfuse_handler]}
    ):
        if "agent" in chunk:
            msg = chunk["agent"]["messages"][0]
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                total_tokens += msg.usage_metadata.get("total_tokens", 0)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_used.append(tc["name"])
                    steps.append(f"🔧 Using tool: `{tc['name']}` with query: `{tc['args']}`")
            else:
                final_answer = msg.content
        elif "tools" in chunk:
            msg = chunk["tools"]["messages"][0]
            steps.append(f"📄 Tool result received from: `{msg.name}`")

    return final_answer, steps, tools_used, total_tokens