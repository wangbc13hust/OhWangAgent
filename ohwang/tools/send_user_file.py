from __future__ import annotations

import os

from .base import BaseTool, ToolResult


class SendUserFileTool(BaseTool):
    name = "send_user_file"
    description = (
        "Present a generated file to the user in the terminal WITHOUT adding its "
        "full contents to the model context. Use after file_write to let the user "
        "review a deliverable (report, doc, outline). Pass a short summary of the "
        "file's key points so the model still knows what it contains."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to show the user.",
            },
            "summary": {
                "type": "string",
                "description": "Short summary of the file contents (shown to user and model).",
            },
        },
        "required": ["file_path", "summary"],
    }
    default_permission = "allow"

    def __init__(self, display=None) -> None:
        self._display = display

    def execute(self, input: dict) -> ToolResult:
        path = input.get("file_path", "")
        summary = input.get("summary", "")
        if not os.path.isfile(path):
            return ToolResult(content=f"File not found: {path}", is_error=True)

        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        if self._display is not None:
            preview = content[:2000]
            suffix = "\n... [truncated] ..." if len(content) > 2000 else ""
            header = f"\n[bold cyan]── {os.path.basename(path)} ({len(content)} chars) ──[/bold cyan]"
            self._display(header)
            self._display(preview + suffix)

        return ToolResult(
            content=(
                f"Shown {os.path.abspath(path)} to user ({len(content)} chars). "
                f"Summary: {summary}"
            )
        )
