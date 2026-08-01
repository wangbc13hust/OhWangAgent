from unittest.mock import patch

from ohwang.tools.web_fetch import WebFetchTool


def test_web_fetch_returns_error_on_bad_url():
    tool = WebFetchTool()
    r = tool.execute({"url": "http://127.0.0.1:1/nonexistent"})
    assert r.is_error is True
    assert "Fetch failed" in r.content


def test_web_fetch_success_with_mock():
    mock_resp = type(
        "Resp",
        (),
        {
            "text": "<html><body><h1>Hello</h1><p>World</p></body></html>",
            "status_code": 200,
            "headers": {"content-type": "text/html"},
        },
    )()
    with patch("ohwang.tools.web_fetch.httpx.get", return_value=mock_resp):
        tool = WebFetchTool()
        r = tool.execute({"url": "https://example.com"})
        assert r.is_error is False
        assert "200" in r.content
        assert "Hello" in r.content


def test_web_fetch_truncation():
    long_body = "<html><body>" + "x" * 30000 + "</body></html>"
    mock_resp = type(
        "Resp",
        (),
        {"text": long_body, "status_code": 200, "headers": {"content-type": "text/html"}},
    )()
    with patch("ohwang.tools.web_fetch.httpx.get", return_value=mock_resp):
        tool = WebFetchTool()
        r = tool.execute({"url": "https://example.com", "max_chars": 1000})
        assert r.is_error is False
        assert "truncated" in r.content


def test_web_fetch_schema():
    tool = WebFetchTool()
    assert tool.name == "web_fetch"
    assert tool.default_permission == "allow"
    assert "url" in tool.input_schema["properties"]


def test_web_fetch_rejects_non_http_scheme():
    tool = WebFetchTool()
    for url in ("file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)"):
        r = tool.execute({"url": url})
        assert r.is_error is True
        assert "scheme" in r.content
        assert "http" in r.content
