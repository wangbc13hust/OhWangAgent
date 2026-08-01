from __future__ import annotations

import time
from collections.abc import Callable

from .base import BaseTool, ToolResult


class BriefTool(BaseTool):
    name = "brief"
    description = (
        "Generate a short progress brief of the current session: tool-call usage, "
        "pending todos, and iteration count. Call before reporting status or when "
        "asked to summarize progress."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "focus": {
                "type": "string",
                "description": "Optional focus area mentioned in the brief.",
            }
        },
        "required": [],
    }
    default_permission = "allow"

    def __init__(
        self,
        usage=None,
        todo_store=None,
        iterations: Callable[[], int] | None = None,
    ) -> None:
        self._usage = usage
        self._todo_store = todo_store
        self._iterations = iterations

    def execute(self, input: dict) -> ToolResult:
        lines = [f"Session brief ({time.strftime('%H:%M:%S')}):"]
        focus = (input.get("focus") or "").strip()
        if focus:
            lines.append(f"  Focus: {focus}")
        n_iter = self._iterations() if self._iterations is not None else None
        lines.append(f"  Iterations: {n_iter if n_iter is not None else '?'}")
        if self._usage is not None:
            lines.append(f"  Tool calls: {self._usage.total}")
            errs = sum(
                self._usage.errors_for(name)
                for name in self._usage._calls  # noqa: SLF001
            )
            lines.append(f"  Tool errors: {errs}")
        if self._todo_store is not None:
            items = self._todo_store.todos
            done = sum(1 for t in items if t.get("status") == "completed")
            pending = len(items) - done
            lines.append(f"  Todos: {done} done, {pending} pending")
        return ToolResult(content="\n".join(lines))
