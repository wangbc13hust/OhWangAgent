from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .base import BaseTool, ToolResult


class SnipTool(BaseTool):
    name = "snip"
    description = (
        "Save a snippet of text (terminal output, logs, excerpts) to .ohwang/snips/ "
        "and return the saved file path. Use to archive output fragments for later."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to save."},
            "title": {
                "type": "string",
                "description": "Optional filename stem (default 'snip').",
            },
        },
        "required": ["text"],
    }
    default_permission = "allow"

    def __init__(self, workdir) -> None:
        self._dir = Path(workdir) / ".ohwang" / "snips"

    def execute(self, input: dict) -> ToolResult:
        text = input.get("text", "")
        title = re.sub(r"[^\w\-. ]+", "_", input.get("title") or "snip").strip() or "snip"
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{title}-{time.strftime('%Y%m%d-%H%M%S')}.txt"
        path.write_text(text, encoding="utf-8")
        return ToolResult(content=f"Saved snippet to {os.path.abspath(path)}.")
