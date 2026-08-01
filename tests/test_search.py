from ohwang.services.search import (
    DuckDuckGoSearch,
    SearchError,
    SearchProvider,
    TavilySearch,
    make_search_provider,
)


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
    try:
        s.search("hello")
    except SearchError as exc:
        assert "unreachable" in str(exc)
    else:
        raise AssertionError("expected SearchError")


def test_duckduckgo_raises_search_error_on_http_error(monkeypatch):
    class Resp:
        status_code = 503

    monkeypatch.setattr(
        "ohwang.services.search.httpx.post", lambda *a, **k: Resp()
    )
    s = DuckDuckGoSearch()
    try:
        s.search("hello")
    except SearchError as exc:
        assert "503" in str(exc)
    else:
        raise AssertionError("expected SearchError")
