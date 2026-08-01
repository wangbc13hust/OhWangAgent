from __future__ import annotations

import os
from pathlib import Path

from .base import BaseTool, ToolResult

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
}


class GlobTool(BaseTool):
    name = "glob"
    description = (
        "Find files matching a glob pattern (e.g. **/*.py). Returns matching "
        "paths relative to the search path. Skips common ignored directories "
        "(.git, .venv, node_modules, etc.)."
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

        if "**" in pattern:
            parts = pattern.split("**")
            prefix = parts[0].lstrip("/\\")
            start = root
            if prefix:
                start = root / prefix
                if not start.is_dir():
                    return ToolResult(content="No files matched.")
            suffix = parts[-1].lstrip("/\\")
            results = []
            for p in start.rglob(suffix or "*"):
                if p.is_dir():
                    continue
                rel = p.relative_to(base)
                if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
                    continue
                results.append(rel.as_posix())
        else:
            results = [
                p.relative_to(base).as_posix()
                for p in root.glob(pattern)
                if not p.is_dir()
            ]

        results = sorted(results)[:500]
        if not results:
            return ToolResult(content="No files matched.")
        return ToolResult(content="\n".join(results))
