from __future__ import annotations

from difflib import SequenceMatcher

from .base import BaseTool, ToolResult
from .registry import ToolRegistry


class ToolSearchTool(BaseTool):
    name = "tool_search"
    description = (
        "Search the available tools by name and description. Useful when the "
        "correct tool is unclear or the tool list is long. Returns ranked matches."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What you want to do, in natural language.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return.",
            },
        },
        "required": ["query"],
    }
    default_permission = "allow"

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, input: dict) -> ToolResult:
        query = str(input["query"]).lower()
        limit = int(input.get("limit", 5))
        scored: list[tuple[float, BaseTool]] = []
        for tool in self._registry:
            if tool.name == self.name:
                continue
            name = tool.name.lower()
            desc = tool.description.lower()
            score = 0.0
            if query in name:
                score += 3.0
            if query in desc:
                score += 1.5
            score += SequenceMatcher(None, query, name).ratio()
            score += SequenceMatcher(None, query, desc).ratio() * 0.5
            if score > 0.4:
                scored.append((score, tool))
        scored.sort(key=lambda t: -t[0])

        lines = [f"Tools matching '{input['query']}':"]
        if not scored:
            lines.append("  No matches found.")
        for score, tool in scored[:limit]:
            desc = (tool.description or "").strip().replace("\n", " ")
            lines.append(
                f"  {tool.name}  [{tool.default_permission}]  {desc[:110]}"
            )
        return ToolResult(content="\n".join(lines))
