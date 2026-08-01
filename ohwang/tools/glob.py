from __future__ import annotations

import os
from pathlib import Path

from .base import BaseTool, ToolResult


class GlobTool(BaseTool):
    name = "glob"
    description = (
        "Find files matching a glob pattern (e.g. **/*.py). Returns matching "
        "paths relative to the search path."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {
                "type": "string",
                "description": "Base directory. Defaults to cwd.",
            },
        },
        "required": ["pattern"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        pattern = input["pattern"]
        base = input.get("path") or os.getcwd()

        root = Path(base)
        if not root.is_dir():
            return ToolResult(content=f"Not a directory: {base}", is_error=True)

        results = sorted(p.relative_to(base).as_posix() for p in root.glob(pattern) if not p.is_dir())
        if not results:
            return ToolResult(content="No files matched.")
        results = results[:500]
        return ToolResult(content="\n".join(results))
