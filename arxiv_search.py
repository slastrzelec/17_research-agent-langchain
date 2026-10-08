"""ArXiv search through the public Atom API (timeouts, defensive parsing)."""
import re

import requests
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

API_URL = "https://export.arxiv.org/api/query"
TIMEOUT_S = 10
MAX_RESULTS = 3
MAX_CHARS = 700
NS = {"a": "http://www.w3.org/2005/Atom"}
HEADERS = {"User-Agent": "scientific-research-agent/2.0 (portfolio demo; github.com/slastrzelec)"}


def build_query(text: str) -> str:
    """Turn free text into an arXiv query: all:term AND all:term (max 8 alphanumeric terms)."""
    terms = re.findall(r"[A-Za-z0-9\-]+", text)[:8]
    return " AND ".join(f"all:{t}" for t in terms)


def _clean(s: str | None) -> str:
    return " ".join((s or "").split())


def search_arxiv(query: str, http=requests) -> tuple[str, list[dict]]:
    """Return (text for the model, sources). Never raises."""
    search_query = build_query(query)
    if not search_query:
        return "No results found on ArXiv.", []
    try:
        resp = http.get(
            API_URL,
            params={"search_query": search_query, "max_results": MAX_RESULTS,
                    "sortBy": "relevance"},
            headers=HEADERS,
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        blocks, sources = [], []
        for entry in root.findall("a:entry", NS):
            title = _clean(entry.findtext("a:title", namespaces=NS))
            url = _clean(entry.findtext("a:id", namespaces=NS))
            summary = _clean(entry.findtext("a:summary", namespaces=NS))[:MAX_CHARS]
            published = _clean(entry.findtext("a:published", namespaces=NS))[:10]
            if not title or not url:
                continue
            authors = [_clean(a.findtext("a:name", namespaces=NS))
                       for a in entry.findall("a:author", NS)][:5]
            blocks.append(f"Title: {title}\nAuthors: {', '.join(authors)}\n"
                          f"Published: {published}\nSummary: {summary}")
            sources.append({"title": title, "url": url.replace("http://", "https://", 1)})
        if not blocks:
            return "No results found on ArXiv.", []
        return "\n\n".join(blocks), sources
    except requests.Timeout:
        return "ArXiv error: request timed out.", []
    except (requests.RequestException, ValueError, ElementTree.ParseError,
            DefusedXmlException) as exc:
        return f"ArXiv error: {type(exc).__name__}", []
