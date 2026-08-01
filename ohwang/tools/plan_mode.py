from __future__ import annotations

from ..modes import Mode
from .base import BaseTool, ToolResult


class EnterPlanModeTool(BaseTool):
    name = "enter_plan_mode"
    description = (
        "Switch to plan mode: read-only. File writes, edits, and shell commands "
        "are disabled. Use to research and propose a plan before making changes."
    )
    input_schema = {"type": "object", "properties": {}}
    default_permission = "allow"

    def __init__(self, permissions) -> None:
        self.permissions = permissions

    def execute(self, input: dict) -> ToolResult:
        self.permissions._plan_prev = self.permissions.mode
        self.permissions.mode = Mode.PLAN
        return ToolResult(
            content="Entered plan mode. Write/bash tools are now disabled; "
            "read-only tools (file_read, grep, glob) still work."
        )


class ExitPlanModeTool(BaseTool):
    name = "exit_plan_mode"
    description = "Exit plan mode and resume normal operation with all tools enabled."
    input_schema = {"type": "object", "properties": {}}
    default_permission = "allow"

    def __init__(self, permissions) -> None:
        self.permissions = permissions

    def execute(self, input: dict) -> ToolResult:
        prev = getattr(self.permissions, "_plan_prev", None)
        self.permissions.mode = prev if prev is not None else Mode.DEFAULT
        self.permissions._plan_prev = None
        return ToolResult(content="Exited plan mode. All tools re-enabled.")
