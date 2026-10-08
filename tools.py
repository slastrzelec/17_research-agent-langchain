"""LangChain tools. Search tools return (text, sources) as content + artifact."""
from langchain_core.tools import tool

from arxiv_search import search_arxiv
from pubmed import search_pubmed
from safe_calc import CalcError, safe_eval
from sources import clean_sources
from wiki import search_wikipedia


@tool(response_format="content_and_artifact")
def wikipedia(query: str) -> tuple[str, list]:
    """Search Wikipedia for general scientific concepts, people and processes."""
    text, sources = search_wikipedia(query)
    return text, clean_sources(sources)


@tool(response_format="content_and_artifact")
def arxiv(query: str) -> tuple[str, list]:
    """Search ArXiv for recent research preprints (physics, maths, CS, ML, quantitative biology)."""
    text, sources = search_arxiv(query)
    return text, clean_sources(sources)


@tool(response_format="content_and_artifact")
def pubmed_search(query: str) -> tuple[str, list]:
    """Search PubMed for biomedical research papers. Use for medical, clinical or biological questions."""
    text, sources = search_pubmed(query)
    return text, clean_sources(sources)


@tool
def calculate(expression: str) -> str:
    """Useful for mathematical calculations. Input should be a mathematical expression."""
    try:
        return str(safe_eval(expression))
    except CalcError as e:
        return f"Error: {e}"


TOOLS = [wikipedia, arxiv, pubmed_search, calculate]
