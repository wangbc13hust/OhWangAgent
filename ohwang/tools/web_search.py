from __future__ import annotations

from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web and return titles, urls, and snippets. "
        "Use for up-to-date information beyond your training data."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    }
    default_permission = "allow"

    def __init__(self, provider) -> None:
        self.provider = provider

    def execute(self, input: dict) -> ToolResult:
        query = input["query"]
        max_results = input.get("max_results", 5)
        try:
            results = self.provider.search(query, max_results)
        except Exception as exc:
            return ToolResult(content=f"Search failed: {exc}", is_error=True)
        if not results:
            return ToolResult(content="No results found.")
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. {r.get('title', '')}\n   {r.get('url', '')}\n   {r.get('snippet', '')}"
            )
        return ToolResult(content="\n".join(lines))
