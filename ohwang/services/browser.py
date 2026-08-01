from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Optional


class BrowserSession:
    """A persistent, headless Chromium session driven by Playwright.

    Lazily launches the browser on first use. All actions are serialized via a
    lock. Raises RuntimeError with install instructions when Playwright is
    missing so callers can degrade gracefully.
    """

    def __init__(self, headless: bool = True, workdir: str | Path | None = None) -> None:
        self.headless = headless
        self.workdir = Path(workdir) if workdir else None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = threading.Lock()

    def _ensure(self):
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && "
                "playwright install chromium"
            ) from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()

    def navigate(self, url: str) -> str:
        with self._lock:
            self._ensure()
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return self._page.title()

    def get_dom(self, max_chars: int = 20000) -> str:
        with self._lock:
            self._ensure()
            text = self._page.content()
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars] ..."

    def screenshot(self) -> str:
        with self._lock:
            self._ensure()
            path = self.workdir if self.workdir else Path.cwd()
            target = Path(path) / f"screenshot_{uuid.uuid4().hex[:8]}.png"
            self._page.screenshot(path=str(target))
            return str(target)

    def click(self, selector: str) -> str:
        with self._lock:
            self._ensure()
            self._page.click(selector, timeout=10000)
            return f"Clicked {selector}"

    def fill(self, selector: str, text: str) -> str:
        with self._lock:
            self._ensure()
            self._page.fill(selector, text, timeout=10000)
            return f"Filled {selector}"

    def scroll(self, direction: str = "down") -> str:
        with self._lock:
            self._ensure()
            delta = 800 if direction == "up" else -800
            self._page.evaluate(
                f"window.scrollBy(0, {delta});"
            )
            return f"Scrolled {direction}"

    def evaluate(self, js: str) -> str:
        with self._lock:
            self._ensure()
            result = self._page.evaluate(js)
            return str(result)

    def close(self) -> None:
        with self._lock:
            if self._page is not None:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._page = self._context = self._browser = None
            pw = getattr(self, "_pw", None)
            if pw is not None:
                try:
                    pw.stop()
                except Exception:
                    pass
                self._pw = None
