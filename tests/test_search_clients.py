import requests

from arxiv_search import build_query, search_arxiv
from sources import clean_sources
from wiki import MAX_CHARS, search_wikipedia


class Resp:
    def __init__(self, json_data=None, content=b"", status=200, bad_json=False):
        self._json, self.content, self.status, self.bad_json = json_data, content, status, bad_json

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(str(self.status))

    def json(self):
        if self.bad_json:
            raise ValueError("bad")
        return self._json


class Http:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.calls = resp, exc, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, timeout))
        if self.exc:
            raise self.exc
        return self.resp


WIKI = {"query": {"pages": {
    "2": {"title": "B", "index": 2, "extract": "second", "fullurl": "https://en.wikipedia.org/wiki/B"},
    "1": {"title": "A", "index": 1, "extract": "x" * 5000, "fullurl": "https://en.wikipedia.org/wiki/A"},
    "3": {"title": "NoText", "index": 3, "extract": "", "fullurl": "https://en.wikipedia.org/wiki/N"},
}}}


def test_wikipedia_orders_truncates_and_returns_sources():
    http = Http(Resp(WIKI))
    text, sources = search_wikipedia("a", http=http)
    assert text.startswith("Page: A") and "Page: B" in text and "NoText" not in text
    assert len(text.split("\n\n")[0]) <= MAX_CHARS + 40
    assert [s["title"] for s in sources] == ["A", "B"]
    assert http.calls[0][2] == 10


def test_wikipedia_failures_never_raise():
    assert "No results" in search_wikipedia("a", http=Http(Resp({"batchcomplete": ""})))[0]
    assert "No results" in search_wikipedia("a", http=Http(Resp([1])))[0]
    assert "error" in search_wikipedia("a", http=Http(Resp(status=500)))[0]
    assert "error" in search_wikipedia("a", http=Http(Resp(bad_json=True)))[0]
    text, sources = search_wikipedia("a", http=Http(exc=requests.Timeout()))
    assert "timed out" in text and sources == []


ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry><id>http://arxiv.org/abs/2401.00001v1</id><title> Graph  networks
  for molecules </title><summary>We study   things.</summary><published>2024-01-01T00:00:00Z</published>
  <author><name>A. One</name></author><author><name>B. Two</name></author></entry>
 <entry><title>no id</title></entry>
</feed>"""


def test_arxiv_parses_atom_and_upgrades_to_https():
    text, sources = search_arxiv("graph networks", http=Http(Resp(content=ATOM)))
    assert "Graph networks for molecules" in text and "A. One, B. Two" in text
    assert sources == [{"title": "Graph networks for molecules",
                        "url": "https://arxiv.org/abs/2401.00001v1"}]


def test_arxiv_rejects_xml_bombs_and_failures():
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><feed>&b;</feed>'
    assert "error" in search_arxiv("x", http=Http(Resp(content=bomb)))[0]
    assert "error" in search_arxiv("x", http=Http(Resp(content=b"not xml")))[0]
    assert "error" in search_arxiv("x", http=Http(Resp(status=503)))[0]
    assert "timed out" in search_arxiv("x", http=Http(exc=requests.Timeout()))[0]
    assert "No results" in search_arxiv("!!!", http=Http(Resp(content=ATOM)))[0]


def test_arxiv_query_builder_strips_operators():
    q = build_query('cat:cs.AI OR "x" ; DROP')
    assert "OR \"" not in q and q.count("all:") == len(q.split(" AND "))
    assert len(build_query("a b c d e f g h i j k").split(" AND ")) == 8


def test_clean_sources_allow_list():
    items = [
        {"title": "ok", "url": "https://arxiv.org/abs/1"},
        {"title": "dup", "url": "https://arxiv.org/abs/1"},
        {"title": "http", "url": "http://arxiv.org/abs/2"},
        {"title": "evil", "url": "https://arxiv.org.evil.com/x"},
        {"title": "js", "url": "javascript:alert(1)"},
        {"title": 5, "url": "https://en.wikipedia.org/wiki/X"},
        "string", None,
        {"title": "", "url": "https://pubmed.ncbi.nlm.nih.gov/1/"},
    ]
    out = clean_sources(items)
    assert [s["url"] for s in out] == ["https://arxiv.org/abs/1", "https://pubmed.ncbi.nlm.nih.gov/1/"]
    assert out[1]["title"] == "https://pubmed.ncbi.nlm.nih.gov/1/"
    assert clean_sources(None) == []


def test_group_sources():
    from sources import group_sources
    items = [{"title": f"w{i}", "url": f"https://en.wikipedia.org/wiki/W{i}"} for i in range(3)]
    items.append({"title": "a", "url": "https://arxiv.org/abs/1"})
    groups = group_sources(items, per_group=2)
    assert [g["label"] for g in groups] == ["📖 Wikipedia", "📄 ArXiv"]
    assert len(groups[0]["shown"]) == 2 and len(groups[0]["extra"]) == 1 and groups[1]["extra"] == []
    assert group_sources([]) == []
