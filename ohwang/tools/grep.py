from __future__ import annotations

import fnmatch
import os
import re

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


class GrepTool(BaseTool):
    name = "grep"
    description = (
        "Search file contents with a regex pattern. Returns matching lines "
        "as path:line:match. Walks the path recursively, skipping common "
        "ignored directories."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression."},
            "path": {
                "type": "string",
                "description": "Directory or file to search. Defaults to cwd.",
            },
            "include": {
                "type": "string",
                "description": "Glob filter for file names, e.g. *.py.",
            },
        },
        "required": ["pattern"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        pattern = input["pattern"]
        path = input.get("path") or os.getcwd()
        include = input.get("include")

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return ToolResult(content=f"Invalid regex: {exc}", is_error=True)

        matches: list[str] = []
        max_matches = 200

        if os.path.isfile(path):
            files = [path]
        else:
            files = []
            for root, dirs, filenames in os.walk(path):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                for fn in filenames:
                    if include and not fnmatch.fnmatch(fn, include):
                        continue
                    files.append(os.path.join(root, fn))
                if len(files) > 5000:
                    break

        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        if regex.search(line):
                            matches.append(
                                f"{fpath}:{lineno}:{line.rstrip()}"
                            )
                            if len(matches) >= max_matches:
                                matches.append(
                                    f"... [stopped at {max_matches} matches]"
                                )
                                return ToolResult(content="\n".join(matches))
            except OSError:
                continue

        if not matches:
            return ToolResult(content="No matches found.")
        return ToolResult(content="\n".join(matches))
