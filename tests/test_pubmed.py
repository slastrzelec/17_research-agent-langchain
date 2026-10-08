import requests

from pubmed import MAX_CHARS, search_pubmed


class Resp:
    def __init__(self, json_data=None, text="", status=200, bad_json=False):
        self._json, self.text, self.status, self.bad_json = json_data, text, status, bad_json

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")

    def json(self):
        if self.bad_json:
            raise ValueError("no json")
        return self._json


class Http:
    def __init__(self, *responses, exc=None):
        self.responses, self.exc, self.calls = list(responses), exc, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if self.exc:
            raise self.exc
        return self.responses.pop(0)


def test_success_truncates_and_uses_timeout():
    http = Http(Resp({"esearchresult": {"idlist": ["1", "2", "x;drop"]}}), Resp(text="x" * 5000),
                Resp({"result": {"1": {"title": "Paper one"}}}))
    out, sources = search_pubmed("cnt", http=http)
    assert len(out) == MAX_CHARS
    assert all(c[2] == 10 for c in http.calls)
    assert http.calls[1][1]["id"] == "1,2"
    assert sources == [{"title": "Paper one", "url": "https://pubmed.ncbi.nlm.nih.gov/1/"},
                       {"title": "PubMed PMID 2", "url": "https://pubmed.ncbi.nlm.nih.gov/2/"}]


def test_titles_failure_still_returns_sources():
    http = Http(Resp({"esearchresult": {"idlist": ["7"]}}), Resp(text="abs"), Resp(status=500))
    out, sources = search_pubmed("q", http=http)
    assert out == "abs" and sources[0]["title"] == "PubMed PMID 7"


def test_no_results():
    http = Http(Resp({"esearchresult": {"idlist": []}}))
    assert search_pubmed("zzz", http=http) == ("No results found on PubMed.", [])


def test_unexpected_json_shapes():
    assert "No results" in search_pubmed("q", http=Http(Resp({"error": "rate limit"})))[0]
    assert "No results" in search_pubmed("q", http=Http(Resp([1, 2, 3])))[0]


def test_http_error_malformed_json_and_timeout():
    assert search_pubmed("q", http=Http(Resp(status=429)))[0].startswith("PubMed error")
    assert search_pubmed("q", http=Http(Resp(bad_json=True)))[0].startswith("PubMed error")
    assert "timed out" in search_pubmed("q", http=Http(exc=requests.Timeout()))[0]
    assert search_pubmed("q", http=Http(exc=requests.ConnectionError()))[0].startswith("PubMed error")
