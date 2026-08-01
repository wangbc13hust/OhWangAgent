from __future__ import annotations

from ..services.worktree import WorktreeManager
from .base import BaseTool, ToolResult


class EnterWorktreeTool(BaseTool):
    name = "enter_worktree"
    description = (
        "Create a git worktree on a new branch for isolated development. "
        "Returns the new directory; work there with absolute paths, then "
        "call exit_worktree to remove it."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "branch": {
                "type": "string",
                "description": "Name of the new branch to create.",
            },
            "path": {
                "type": "string",
                "description": "Optional path for the worktree (defaults to sibling dir).",
            },
        },
        "required": ["branch"],
    }
    default_permission = "ask"

    def __init__(self, manager: WorktreeManager) -> None:
        self._manager = manager

    def execute(self, input: dict) -> ToolResult:
        ok, message = self._manager.add(input["branch"], input.get("path"))
        return ToolResult(content=message, is_error=not ok)


class ExitWorktreeTool(BaseTool):
    name = "exit_worktree"
    description = "Remove the worktree created in this session (git worktree remove --force)."
    input_schema = {"type": "object", "properties": {}}
    default_permission = "ask"

    def __init__(self, manager: WorktreeManager) -> None:
        self._manager = manager

    def execute(self, input: dict) -> ToolResult:
        ok, message = self._manager.remove()
        return ToolResult(content=message, is_error=not ok)
