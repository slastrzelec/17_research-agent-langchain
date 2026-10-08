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
    http = Http(Resp({"esearchresult": {"idlist": ["1", "2"]}}), Resp(text="x" * 5000))
    out = search_pubmed("cnt", http=http)
    assert len(out) == MAX_CHARS
    assert all(c[2] == 10 for c in http.calls)
    assert http.calls[1][1]["id"] == "1,2"


def test_no_results():
    assert "No results" in search_pubmed("zzz", http=Http(Resp({"esearchresult": {"idlist": []}})))


def test_unexpected_json_shapes():
    assert "No results" in search_pubmed("q", http=Http(Resp({"error": "rate limit"})))
    assert "No results" in search_pubmed("q", http=Http(Resp([1, 2, 3])))


def test_http_error_malformed_json_and_timeout():
    assert search_pubmed("q", http=Http(Resp(status=429))).startswith("PubMed error")
    assert search_pubmed("q", http=Http(Resp(bad_json=True))).startswith("PubMed error")
    assert "timed out" in search_pubmed("q", http=Http(exc=requests.Timeout()))
    assert search_pubmed("q", http=Http(exc=requests.ConnectionError())).startswith("PubMed error")
