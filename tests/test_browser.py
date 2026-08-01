import sys
import types
from pathlib import Path

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


# ---------- Fake Playwright to exercise full action surface ----------

class _FakePage:
    def __init__(self):
        self.title_val = "Fake Page"
        self.content_val = "<html><title>Fake Page</title></html>"
        self.goto_calls = []
        self.screenshot_calls = []
        self.click_calls = []
        self.fill_calls = []
        self.evaluate_calls = []

    def goto(self, url, **kw):
        self.goto_calls.append(url)

    def title(self):
        return self.title_val

    def content(self):
        return self.content_val

    def screenshot(self, path=None):
        self.screenshot_calls.append(path)

    def click(self, selector, **kw):
        self.click_calls.append(selector)

    def fill(self, selector, text, **kw):
        self.fill_calls.append((selector, text))

    def evaluate(self, js):
        self.evaluate_calls.append(js)
        return "js-result"


class _FakeContext:
    def __init__(self):
        self.page = _FakePage()

    def new_page(self):
        return self.page


class _FakeBrowser:
    def __init__(self):
        self.context = _FakeContext()
        self.closed = False

    def new_context(self):
        return self.context

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    def launch(self, **kw):
        return self.browser


class _FakePW:
    def __init__(self, browser):
        self.browser = browser
        self.stopped = False
        self.chromium = _FakeChromium(browser)

    def stop(self):
        self.stopped = True


class _FakePlaywright:
    def __init__(self, browser):
        self.browser = browser
        self.started = False

    def start(self):
        self.started = True
        return _FakePW(self.browser)


def _make_session(monkeypatch, tmp_path, browser=None):
    browser = browser or _FakeBrowser()
    fake = _FakePlaywright(browser)
    fake_pkg = types.ModuleType("playwright")
    fake_sync = types.ModuleType("playwright.sync_api")
    fake_sync.sync_playwright = lambda: fake
    monkeypatch.setitem(sys.modules, "playwright", fake_pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync)
    return BrowserSession(headless=True, workdir=str(tmp_path)), browser


def test_browser_navigate_returns_title(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    title = session.navigate("https://example.com")
    assert title == "Fake Page"
    assert browser.context.page.goto_calls == ["https://example.com"]


def test_browser_get_dom_truncates(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    page = browser.context.page
    page.content_val = "x" * 50000
    dom = session.get_dom(max_chars=1000)
    assert "truncated" in dom


def test_browser_get_dom_short(monkeypatch, tmp_path):
    session, _ = _make_session(monkeypatch, tmp_path)
    dom = session.get_dom()
    assert "Fake Page" in dom
    assert "truncated" not in dom


def test_browser_screenshot_creates_file(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    path = session.screenshot()
    assert Path(path).parent == Path(tmp_path)
    assert Path(path).suffix == ".png"
    assert len(browser.context.page.screenshot_calls) == 1


def test_browser_click_and_fill(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    page = browser.context.page
    assert session.click("#btn") == "Clicked #btn"
    assert page.click_calls == ["#btn"]
    assert session.fill("#in", "hi") == "Filled #in"
    assert page.fill_calls == [("#in", "hi")]


def test_browser_scroll_directions(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    page = browser.context.page
    session.scroll("up")
    session.scroll("down")
    assert "scrollBy(0, 800" in page.evaluate_calls[0]
    assert "scrollBy(0, -800" in page.evaluate_calls[1]


def test_browser_evaluate_returns_string(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    assert session.evaluate("1+1") == "js-result"
    assert browser.context.page.evaluate_calls == ["1+1"]


def test_browser_close_stops_playwright(monkeypatch, tmp_path):
    session, browser = _make_session(monkeypatch, tmp_path)
    session.navigate("https://example.com")
    session.close()
    assert browser.closed
    assert session._page is None
    assert session._pw is None


# ---------- WebBrowserTool dispatch ----------

def _tool(monkeypatch, tmp_path, browser=None):
    session, browser = _make_session(monkeypatch, tmp_path, browser)
    return WebBrowserTool(session), browser


def test_tool_all_actions(monkeypatch, tmp_path):
    tool, browser = _tool(monkeypatch, tmp_path)
    r = tool.execute({"action": "navigate", "url": "https://x.com"})
    assert not r.is_error and "Fake Page" in r.content
    r = tool.execute({"action": "dom"})
    assert not r.is_error and "Fake Page" in r.content
    r = tool.execute({"action": "screenshot"})
    assert not r.is_error and "Screenshot saved" in r.content
    r = tool.execute({"action": "click", "selector": "#b"})
    assert not r.is_error and "Clicked #b" in r.content
    r = tool.execute({"action": "fill", "selector": "#i", "text": "t"})
    assert not r.is_error and "Filled #i" in r.content
    r = tool.execute({"action": "scroll"})
    assert not r.is_error and "Scrolled down" in r.content
    r = tool.execute({"action": "evaluate", "js": "1"})
    assert not r.is_error and "js-result" in r.content


def test_tool_wraps_session_error(monkeypatch, tmp_path):
    class _BoomPage(_FakePage):
        def goto(self, url, **kw):
            raise RuntimeError("boom page")

    browser = _FakeBrowser()
    browser.context.page = _BoomPage()
    tool, _ = _tool(monkeypatch, tmp_path, browser)
    r = tool.execute({"action": "navigate", "url": "https://x.com"})
    assert r.is_error
    assert "boom page" in r.content
