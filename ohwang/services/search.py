from __future__ import annotations

import html as html_mod
import os
import re
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import unquote

import httpx


class SearchError(Exception):
    """Raised when a search backend fails (network/HTTP), not when no results."""


class SearchProvider(ABC):
    name = "base"

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Return a list of {title, url, snippet} dicts.

        Raises SearchError when the backend is unreachable; returns [] only
        when the query genuinely has no results.
        """


class DuckDuckGoSearch(SearchProvider):
    name = "duckduckgo"

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        try:
            resp = httpx.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=15,
                follow_redirects=True,
            )
        except Exception as exc:
            raise SearchError(f"DuckDuckGo unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise SearchError(f"DuckDuckGo returned HTTP {resp.status_code}")
        return self._parse(resp.text, max_results)

    @staticmethod
    def _parse(text: str, max_results: int) -> list[dict]:
        results: list[dict] = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            r".*?<a[^>]+class=\"result__snippet\"[^>]*>(.*?)</a>",
            re.S,
        )
        for m in pattern.finditer(text):
            url = DuckDuckGoSearch._unwrap(html_mod.unescape(m.group(1)))
            title = re.sub(r"<[^>]+>", "", m.group(2))
            snippet = re.sub(r"<[^>]+>", "", m.group(3))
            results.append(
                {
                    "title": html_mod.unescape(title).strip(),
                    "url": url,
                    "snippet": html_mod.unescape(snippet).strip(),
                }
            )
            if len(results) >= max_results:
                break
        return results

    @staticmethod
    def _unwrap(url: str) -> str:
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            return unquote(m.group(1))
        if url.startswith("//"):
            return "https:" + url
        return url


class TavilySearch(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise SearchError(f"Tavily unreachable: {exc}") from exc
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in data.get("results", [])
        ][:max_results]


def make_search_provider() -> Optional[SearchProvider]:
    tavily = os.environ.get("TAVILY_API_KEY")
    if tavily:
        return TavilySearch(tavily)
    return DuckDuckGoSearch()
