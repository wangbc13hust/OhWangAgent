from ohwang.services.search import DuckDuckGoSearch, TavilySearch, make_search_provider


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
