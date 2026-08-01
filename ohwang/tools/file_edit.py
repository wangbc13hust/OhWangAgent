from __future__ import annotations

import os

from .base import BaseTool, ToolResult


class FileEditTool(BaseTool):
    name = "file_edit"
    description = (
        "Replace an exact string in a file. old_string must be unique unless "
        "replace_all is true. Fails if old_string is not found or is ambiguous."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
            "replace_all": {"type": "boolean"},
        },
        "required": ["file_path", "old_string", "new_string"],
    }
    default_permission = "ask"

    def execute(self, input: dict) -> ToolResult:
        path = input["file_path"]
        old = input["old_string"]
        new = input["new_string"]
        replace_all = input.get("replace_all", False)

        if not os.path.isfile(path):
            return ToolResult(content=f"File not found: {path}", is_error=True)
        if not old:
            return ToolResult(content="old_string must be non-empty.", is_error=True)

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        count = content.count(old)
        if count == 0:
            return ToolResult(content="old_string not found in file.", is_error=True)
        if count > 1 and not replace_all:
            return ToolResult(
                content=f"old_string found {count} times; set replace_all=true or add more context.",
                is_error=True,
            )

        new_content = content.replace(old, new) if replace_all else content.replace(
            old, new, 1
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except OSError as exc:
            return ToolResult(content=f"Cannot write file: {exc}", is_error=True)

        replaced = count if replace_all else 1
        return ToolResult(content=f"Replaced {replaced} occurrence(s) in {path}.")
