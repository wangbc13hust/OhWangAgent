from __future__ import annotations

import os

from .base import BaseTool, ToolResult


class FileReadTool(BaseTool):
    name = "file_read"
    description = (
        "Read a text file and return its contents. Supports optional line "
        "offset and limit for large files."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "offset": {
                "type": "integer",
                "description": "1-indexed line to start reading from.",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of lines to read.",
            },
        },
        "required": ["file_path"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        path = input["file_path"]
        offset = input.get("offset")
        limit = input.get("limit")

        if not os.path.isfile(path):
            return ToolResult(content=f"File not found: {path}", is_error=True)

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        start = (offset - 1) if offset and offset > 0 else 0
        end = (start + limit) if limit else len(lines)
        selected = lines[start:end]

        numbered = "".join(
            f"{start + i + 1}: {line}" for i, line in enumerate(selected)
        )
        return ToolResult(content=numbered or "(empty file)")
