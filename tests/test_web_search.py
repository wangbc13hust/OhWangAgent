from ohwang.tools.web_search import WebSearchTool
from tests.helpers import MockSearchProvider


def test_web_search_returns_results():
    provider = MockSearchProvider()
    tool = WebSearchTool(provider)
    r = tool.execute({"query": "python testing"})
    assert r.is_error is False
    assert "python testing" in r.content
    assert "https://example.com" in r.content


def test_web_search_empty_results():
    class EmptyProvider:
        name = "empty"
        def search(self, query, max_results=5):
            return []

    tool = WebSearchTool(EmptyProvider())
    r = tool.execute({"query": "xyz"})
    assert r.is_error is False
    assert "No results" in r.content


def test_web_search_handles_provider_error():
    class FailProvider:
        name = "fail"
        def search(self, query, max_results=5):
            raise RuntimeError("network down")

    tool = WebSearchTool(FailProvider())
    r = tool.execute({"query": "test"})
    assert r.is_error is True
    assert "Search failed" in r.content


def test_web_search_schema():
    tool = WebSearchTool(MockSearchProvider())
    assert tool.name == "web_search"
    assert tool.default_permission == "allow"
    assert "query" in tool.input_schema["properties"]
