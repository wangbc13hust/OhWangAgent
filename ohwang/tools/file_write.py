from __future__ import annotations

import os

from .base import BaseTool, ToolResult


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Create or overwrite a file with the given content. Creates parent directories."
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["file_path", "content"],
    }
    default_permission = "ask"

    def execute(self, input: dict) -> ToolResult:
        path = input["file_path"]
        content = input["content"]

        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

        existed = os.path.isfile(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as exc:
            return ToolResult(content=f"Cannot write file: {exc}", is_error=True)

        action = "Overwrote" if existed else "Created"
        return ToolResult(content=f"{action} {path} ({len(content)} bytes)")
