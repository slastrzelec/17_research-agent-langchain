"""PubMed search through NCBI E-utilities, with timeouts and defensive parsing."""
import requests

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TIMEOUT_S = 10
MAX_RESULTS = 3
MAX_CHARS = 3000


def _titles(ids: list[str], http) -> dict[str, str]:
    """Best-effort PMID -> title; any failure just yields no titles."""
    try:
        resp = http.get(ESUMMARY_URL, params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
                        timeout=TIMEOUT_S)
        resp.raise_for_status()
        result = resp.json().get("result", {})
        return {i: result[i]["title"] for i in ids
                if isinstance(result.get(i), dict) and isinstance(result[i].get("title"), str)}
    except (requests.RequestException, ValueError, AttributeError, KeyError):
        return {}


def search_pubmed(query: str, http=requests) -> tuple[str, list[dict]]:
    """Return (abstracts as text, sources). Never raises."""
    try:
        resp = http.get(
            ESEARCH_URL,
            params={"db": "pubmed", "term": query, "retmax": MAX_RESULTS, "retmode": "json"},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_ids = data.get("esearchresult", {}).get("idlist", []) if isinstance(data, dict) else []
        ids = [i for i in raw_ids if isinstance(i, str) and i.isdigit()]
        if not ids:
            return "No results found on PubMed.", []

        resp = http.get(
            EFETCH_URL,
            params={"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "text"},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        text = resp.text[:MAX_CHARS] or "No abstract text returned by PubMed."
        titles = _titles(ids, http)
        sources = [{"title": titles.get(i, f"PubMed PMID {i}"),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{i}/"} for i in ids]
        return text, sources
    except requests.Timeout:
        return "PubMed error: request timed out.", []
    except (requests.RequestException, ValueError) as exc:
        return f"PubMed error: {type(exc).__name__}", []
