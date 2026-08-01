from __future__ import annotations

from .base import BaseTool, ToolResult

_STATUS_MARK = {"pending": " ", "in_progress": "*", "completed": "x"}


class TodoStore:
    """In-memory todo list shared between the tool and the agent's context."""

    def __init__(self) -> None:
        self.todos: list[dict] = []

    def set(self, todos: list[dict]) -> None:
        self.todos = todos

    def render(self) -> str:
        if not self.todos:
            return ""
        lines = ["\n\n# Current Todo List"]
        for i, t in enumerate(self.todos, 1):
            mark = _STATUS_MARK.get(t.get("status", "pending"), " ")
            lines.append(
                f"{i}. [{mark}] {t.get('content', '')} "
                f"(priority: {t.get('priority', 'medium')})"
            )
        return "\n".join(lines)


class TodoWriteTool(BaseTool):
    name = "todo_write"
    description = (
        "Create or update the task list for multi-step work. Pass the FULL list "
        "each call. Each item: {content, status: pending|in_progress|completed, "
        "priority: high|medium|low}."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["content", "status", "priority"],
                },
            }
        },
        "required": ["todos"],
    }
    default_permission = "allow"

    def __init__(self, store: TodoStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        todos = input.get("todos", [])
        norm = [
            {
                "content": t.get("content", ""),
                "status": t.get("status", "pending"),
                "priority": t.get("priority", "medium"),
            }
            for t in todos
        ]
        self.store.set(norm)
        if not norm:
            return ToolResult(content="Todo list cleared.")
        return ToolResult(content="Todos updated:\n" + self.store.render())
