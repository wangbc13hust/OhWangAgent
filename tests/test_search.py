import pytest

from ohwang.services.search import (
    DuckDuckGoSearch,
    SearchError,
    SearchProvider,
    TavilySearch,
    make_search_provider,
)

DDG_HTML = """
<html><body>
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdoc">Example <b>Title</b></a>
<a rel="nofollow" class="result__snippet">A snippet about <b>stuff</b>.</a>
<a rel="nofollow" class="result__a" href="https://plain.com/page">Plain</a>
<a rel="nofollow" class="result__snippet">Second result snippet.</a>
</body></html>
"""


def test_duckduckgo_search_provider_name():
    s = DuckDuckGoSearch()
    assert s.name == "duckduckgo"


def test_tavily_search_provider_name():
    s = TavilySearch(api_key="test-key")
    assert s.name == "tavily"


def test_make_search_provider_returns_duckduckgo_by_default():
    provider = make_search_provider()
    assert provider is not None
    assert provider.name == "duckduckgo"


def test_make_search_provider_returns_tavily_with_env(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    provider = make_search_provider()
    assert provider.name == "tavily"


def test_duckduckgo_raises_search_error_on_network_failure(monkeypatch):
    import httpx

    def boom(*args, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(httpx, "post", boom)
    s = DuckDuckGoSearch()
    with pytest.raises(SearchError, match="unreachable"):
        s.search("hello")


def test_duckduckgo_raises_search_error_on_http_error(monkeypatch):
    class Resp:
        status_code = 503

    monkeypatch.setattr(
        "ohwang.services.search.httpx.post", lambda *a, **k: Resp()
    )
    s = DuckDuckGoSearch()
    with pytest.raises(SearchError, match="503"):
        s.search("hello")


def test_duckduckgo_parse_results():
    results = DuckDuckGoSearch._parse(DDG_HTML, 5)
    assert len(results) == 2
    r0 = results[0]
    assert r0["title"] == "Example Title"
    assert r0["url"] == "https://example.com/doc"
    assert r0["snippet"] == "A snippet about stuff."
    assert results[1]["url"] == "https://plain.com/page"


def test_duckduckgo_parse_respects_max_results():
    results = DuckDuckGoSearch._parse(DDG_HTML, 1)
    assert len(results) == 1


def test_duckduckgo_parse_empty():
    assert DuckDuckGoSearch._parse("<html>no results</html>", 5) == []


def test_duckduckgo_search_success(monkeypatch):
    class Resp:
        status_code = 200
        text = DDG_HTML

    monkeypatch.setattr(
        "ohwang.services.search.httpx.post", lambda *a, **k: Resp()
    )
    s = DuckDuckGoSearch()
    results = s.search("hello", max_results=5)
    assert len(results) == 2


def test_duckduckgo_unwrap_uddg():
    url = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fa%3Fb%3D1&rut=zzz"
    assert DuckDuckGoSearch._unwrap(url) == "https://example.org/a?b=1"


def test_duckduckgo_unwrap_plain():
    assert DuckDuckGoSearch._unwrap("https://x.com/y") == "https://x.com/y"


def test_tavily_search_success(monkeypatch):
    class Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {"title": "T1", "url": "https://t1", "content": "c1"},
                    {"title": "T2", "url": "https://t2", "content": "c2"},
                ]
            }

    monkeypatch.setattr(
        "ohwang.services.search.httpx.post", lambda *a, **k: Resp()
    )
    s = TavilySearch(api_key="k")
    results = s.search("q", max_results=5)
    assert results[0] == {"title": "T1", "url": "https://t1", "snippet": "c1"}
    assert len(results) == 2


def test_tavily_search_respects_max_results(monkeypatch):
    class Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"title": f"T{i}", "url": f"u{i}", "content": "c"} for i in range(5)]}

    monkeypatch.setattr(
        "ohwang.services.search.httpx.post", lambda *a, **k: Resp()
    )
    s = TavilySearch(api_key="k")
    results = s.search("q", max_results=2)
    assert len(results) == 2


def test_tavily_raises_search_error_on_failure(monkeypatch):
    class Resp:
        def raise_for_status(self):
            raise RuntimeError("http 500")

    monkeypatch.setattr(
        "ohwang.services.search.httpx.post", lambda *a, **k: Resp()
    )
    s = TavilySearch(api_key="k")
    with pytest.raises(SearchError, match="unreachable"):
        s.search("q")
