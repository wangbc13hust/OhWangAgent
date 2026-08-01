from __future__ import annotations

import os

from .base import BaseTool, ToolResult


class MultiEditTool(BaseTool):
    name = "multi_edit"
    description = (
        "Apply the same (or different) string replacements across MULTIPLE files "
        "in one call. Each entry: {file_path, old_string, new_string, replace_all?}. "
        "Set preview=true to return per-file diffs WITHOUT writing; apply=true "
        "writes all edits. Use for batch edits across several documents."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "edits": {
                "type": "array",
                "description": "List of edits, one per file/occurrence.",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                        "replace_all": {"type": "boolean"},
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            },
            "preview": {"type": "boolean", "description": "Show diffs without writing."},
            "apply": {"type": "boolean", "description": "Write edits to files."},
        },
        "required": ["edits"],
    }
    default_permission = "ask"

    def _apply_one(self, path: str, old: str, new: str, replace_all: bool) -> tuple[str, bool]:
        if not os.path.isfile(path):
            return f"  SKIP {path}: file not found", False
        if not old:
            return f"  SKIP {path}: empty old_string", False
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except OSError as exc:
            return f"  SKIP {path}: {exc}", False
        count = content.count(old)
        if count == 0:
            return f"  SKIP {path}: old_string not found", False
        if count > 1 and not replace_all:
            return f"  SKIP {path}: {count} occurrences (set replace_all)", False
        new_content = content.replace(old, new) if replace_all else content.replace(old, new, 1)
        return new_content, True

    def execute(self, input: dict) -> ToolResult:
        edits = input.get("edits", [])
        if not edits:
            return ToolResult(content="No edits provided.", is_error=True)
        # Only an explicit apply=true writes; preview=false must never imply a write.
        apply = bool(input.get("apply", False))

        lines: list[str] = []
        all_ok = True
        for e in edits:
            path = e.get("file_path", "")
            old = e.get("old_string", "")
            new = e.get("new_string", "")
            replace_all = bool(e.get("replace_all", False))
            result, ok = self._apply_one(path, old, new, replace_all)
            if not ok:
                lines.append(result)
                all_ok = False
                continue
            if apply:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(result)
                    lines.append(f"  OK {path}")
                except OSError as exc:
                    lines.append(f"  FAIL {path}: {exc}")
                    all_ok = False
            else:
                lines.append(f"  PREVIEW {path}: would replace '{old}' -> '{new}'")
        return ToolResult(content="\n".join(lines), is_error=not all_ok and apply)
