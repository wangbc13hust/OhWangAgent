from __future__ import annotations

import difflib
import os

from .base import BaseTool, ToolResult


def make_unified_diff(old_text: str, new_text: str, label: str = "file") -> str:
    """Produce a unified diff between two strings (no external deps)."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines, new_lines, fromfile=f"{label} (before)", tofile=f"{label} (after)"
        )
    )


class FileDiffTool(BaseTool):
    name = "file_diff"
    description = (
        "Preview a unified diff for a proposed edit WITHOUT modifying the file. "
        "Pass the current file path and the new content to see exactly what would "
        "change. Use before file_edit to review changes before applying."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "new_content": {
                "type": "string",
                "description": "Proposed replacement content for the file.",
            },
        },
        "required": ["file_path", "new_content"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        path = input.get("file_path", "")
        new_content = input.get("new_content", "")
        if not os.path.isfile(path):
            return ToolResult(content=f"File not found: {path}", is_error=True)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                old_content = f.read()
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        diff = make_unified_diff(old_content, new_content, label=os.path.basename(path))
        if not diff.strip():
            return ToolResult(content="No differences (new content identical to file).")
        return ToolResult(content=diff)


class FilePreviewEditTool(BaseTool):
    name = "file_preview_edit"
    description = (
        "Preview and apply a proposed edit. Set preview=true to return a unified "
        "diff without writing; set apply=true to write the new content. Use "
        "preview first, review the diff, then apply — avoids accidental edits."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "new_content": {
                "type": "string",
                "description": "Full replacement content for the file.",
            },
            "preview": {
                "type": "boolean",
                "description": "Only show diff, do not write (default true).",
            },
            "apply": {
                "type": "boolean",
                "description": "Write the new content to the file.",
            },
        },
        "required": ["file_path", "new_content"],
    }
    default_permission = "ask"

    def execute(self, input: dict) -> ToolResult:
        path = input.get("file_path", "")
        new_content = input.get("new_content", "")
        # Only an explicit apply=true writes; preview=false must never imply a write.
        apply = bool(input.get("apply", False))
        if not os.path.isfile(path):
            return ToolResult(content=f"File not found: {path}", is_error=True)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                old_content = f.read()
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        diff = make_unified_diff(old_content, new_content, label=os.path.basename(path))
        if apply:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except OSError as exc:
                return ToolResult(content=f"Cannot write file: {exc}", is_error=True)
            return ToolResult(content=f"Applied edit to {path}:\n{diff}")
        if not diff.strip():
            return ToolResult(content="No differences (new content identical to file).")
        return ToolResult(content=f"Preview (not applied) — review the diff:\n{diff}")
