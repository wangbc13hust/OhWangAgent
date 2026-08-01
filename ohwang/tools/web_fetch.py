from __future__ import annotations

from urllib.parse import urlparse

import httpx
from markdownify import markdownify as md

from .base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = (
        "Fetch a URL and return its content as markdown. Use for reading "
        "docs, pages, or raw files from the web."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {
                "type": "integer",
                "description": "Max chars to return (default 20000).",
            },
        },
        "required": ["url"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        url = input["url"]
        max_chars = input.get("max_chars", 20000)
        scheme = urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            return ToolResult(
                content=f"Unsupported URL scheme '{scheme}': only http/https are allowed.",
                is_error=True,
            )
        try:
            resp = httpx.get(
                url,
                timeout=20,
                follow_redirects=True,
                headers={
                    "User-Agent": "OhWangAgent/0.1 (+https://github.com/wbc961101/OhWangAgent)"
                },
            )
        except Exception as exc:
            return ToolResult(content=f"Fetch failed: {exc}", is_error=True)

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            text = md(resp.text, heading_style="ATX", bullets="-")
        else:
            text = resp.text

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"
        return ToolResult(content=f"[{resp.status_code} {url}]\n{text}")
