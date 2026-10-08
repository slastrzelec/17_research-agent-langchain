"""PubMed search through NCBI E-utilities, with timeouts and defensive parsing."""
import requests

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TIMEOUT_S = 10
MAX_RESULTS = 3
MAX_CHARS = 3000


def search_pubmed(query: str, http=requests) -> str:
    """Return abstracts of the top PubMed hits as text, or a short error message."""
    try:
        resp = http.get(
            ESEARCH_URL,
            params={"db": "pubmed", "term": query, "retmax": MAX_RESULTS, "retmode": "json"},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        ids = data.get("esearchresult", {}).get("idlist", []) if isinstance(data, dict) else []
        if not ids:
            return "No results found on PubMed."

        resp = http.get(
            EFETCH_URL,
            params={"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "text"},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.text[:MAX_CHARS] or "No abstract text returned by PubMed."
    except requests.Timeout:
        return "PubMed error: request timed out."
    except (requests.RequestException, ValueError) as exc:
        return f"PubMed error: {type(exc).__name__}"
