from __future__ import annotations

from .base import BaseTool, ToolResult


class MemoryReadTool(BaseTool):
    name = "memory_read"
    description = (
        "Read project memory: CLAUDE.md/AGENTS.md context + stored facts. "
        "Use to recall project conventions, decisions, and key information."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to filter facts (optional).",
            },
        },
    }
    default_permission = "allow"

    def __init__(self, store) -> None:
        self._store = store

    def execute(self, input: dict) -> ToolResult:
        query = input.get("query", "")
        if query:
            results = self._store.search_facts(query)
            if not results:
                ctx = self._store.load_project_context()
                if ctx:
                    return ToolResult(content=f"(No matching facts. Project context:)\n{ctx}")
                return ToolResult(content="No matching facts found.")
            lines = [f"- **{r['key']}**: {r['value']}" for r in results]
            return ToolResult(content="\n".join(lines))
        return ToolResult(content=self._store.render_context())


class MemoryWriteTool(BaseTool):
    name = "memory_write"
    description = (
        "Save a fact to project memory for future sessions. "
        "Use to record important decisions, conventions, or gotchas."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Fact identifier (e.g. 'auth_pattern')."},
            "value": {"type": "string", "description": "The fact content."},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags for categorization.",
            },
        },
        "required": ["key", "value"],
    }
    default_permission = "ask"

    def __init__(self, store) -> None:
        self._store = store

    def execute(self, input: dict) -> ToolResult:
        key = input["key"]
        value = input["value"]
        tags = input.get("tags", [])
        self._store.add_fact(key, value, tags)
        return ToolResult(content=f"Saved fact: {key}")
