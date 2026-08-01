from __future__ import annotations

import os

from .base import BaseTool, ToolResult


class LSPDiagnoseTool(BaseTool):
    name = "lsp_diagnose"
    description = (
        "Run LSP diagnostics on a file and return errors/warnings. "
        "Use to catch type errors, lint issues, and other problems "
        "before running tests."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
        },
        "required": ["file_path"],
    }
    default_permission = "allow"

    def __init__(self, client=None) -> None:
        self._client = client

    def execute(self, input: dict) -> ToolResult:
        if self._client is None:
            return ToolResult(
                content="LSP not configured. Add an LSP server to .ohwang/lsp.json.",
                is_error=True,
            )
        path = input["file_path"]
        if not os.path.isfile(path):
            return ToolResult(content=f"File not found: {path}", is_error=True)
        try:
            diags = self._client.diagnose(path)
        except Exception as exc:
            return ToolResult(content=f"LSP error: {exc}", is_error=True)
        if not diags:
            return ToolResult(content=f"No issues found in {path}.")
        lines = [f"{d['severity'].upper()} line {d['line']}: {d['message']}" for d in diags]
        return ToolResult(content=f"Diagnostics for {path}:\n" + "\n".join(lines))
