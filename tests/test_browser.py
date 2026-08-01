import sys

from ohwang.services.browser import BrowserSession
from ohwang.tools.web_browser import WebBrowserTool


def test_browser_missing_playwright_reports_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    session = BrowserSession()
    tool = WebBrowserTool(session)
    result = tool.execute({"action": "navigate", "url": "https://example.com"})
    assert result.is_error
    assert "pip install playwright" in result.content


def test_browser_unknown_action():
    session = BrowserSession()
    tool = WebBrowserTool(session)
    result = tool.execute({"action": "explode"})
    assert result.is_error
    assert "Unknown action" in result.content


def test_browser_close_without_start_no_crash():
    session = BrowserSession()
    session.close()
