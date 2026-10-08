"""Source links returned by the tools (never parsed from model text)."""
from urllib.parse import urlsplit

ALLOWED_HOSTS = {"en.wikipedia.org", "arxiv.org", "pubmed.ncbi.nlm.nih.gov"}
MAX_TITLE = 200


def clean_sources(items) -> list[dict]:
    """Keep only well-formed https links on allow-listed hosts; de-duplicate by URL."""
    out, seen = [], set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url, title = item.get("url"), item.get("title")
        if not isinstance(url, str) or not isinstance(title, str):
            continue
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS or url in seen:
            continue
        seen.add(url)
        out.append({"title": title.strip()[:MAX_TITLE] or url, "url": url})
    return out
