"""Wikipedia search through the MediaWiki Action API (timeouts, defensive parsing)."""
import requests

API_URL = "https://en.wikipedia.org/w/api.php"
TIMEOUT_S = 10
MAX_RESULTS = 2
MAX_CHARS = 1500
HEADERS = {"User-Agent": "scientific-research-agent/2.0 (portfolio demo; github.com/slastrzelec)"}


def search_wikipedia(query: str, http=requests) -> tuple[str, list[dict]]:
    """Return (text for the model, sources). Never raises."""
    try:
        resp = http.get(
            API_URL,
            params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": query, "gsrlimit": MAX_RESULTS, "prop": "extracts|info",
                "exintro": 1, "explaintext": 1, "exlimit": MAX_RESULTS, "inprop": "url",
            },
            headers=HEADERS,
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        pages = (data.get("query") or {}).get("pages") if isinstance(data, dict) else None
        if not isinstance(pages, dict) or not pages:
            return "No results found on Wikipedia.", []
        ordered = sorted((p for p in pages.values() if isinstance(p, dict)),
                         key=lambda p: p.get("index", 0))
        blocks, sources = [], []
        for page in ordered:
            title, extract, url = page.get("title"), page.get("extract"), page.get("fullurl")
            if not isinstance(title, str) or not isinstance(extract, str) or not extract.strip():
                continue
            blocks.append(f"Page: {title}\nSummary: {extract.strip()[:MAX_CHARS]}")
            if isinstance(url, str):
                sources.append({"title": title, "url": url})
        if not blocks:
            return "No results found on Wikipedia.", []
        return "\n\n".join(blocks), sources
    except requests.Timeout:
        return "Wikipedia error: request timed out.", []
    except (requests.RequestException, ValueError) as exc:
        return f"Wikipedia error: {type(exc).__name__}", []
