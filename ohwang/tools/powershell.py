from __future__ import annotations

import os
import shutil
import subprocess

from .base import BaseTool, ToolResult


class PowerShellTool(BaseTool):
    name = "powershell"
    description = (
        "Execute a PowerShell command or script and return stdout+stderr. "
        "Preferred over bash on Windows for cmdlets, pipeline, and .NET interop. "
        "Uses pwsh (PowerShell 7) when available, otherwise powershell.exe."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The PowerShell code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds before killing the command.",
            },
        },
        "required": ["command"],
    }
    default_permission = "ask"

    def execute(self, input: dict) -> ToolResult:
        command = input["command"]
        timeout = input.get("timeout", 120)
        exe = shutil.which("pwsh") or "powershell.exe"
        cmd = [
            exe,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Command timed out after {timeout}s.", is_error=True
            )

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        combined = stdout
        if stderr:
            combined += ("\n--- stderr ---\n" + stderr) if stdout else stderr

        combined = self._truncate(combined)
        header = f"[exit code {proc.returncode}]\n"
        return ToolResult(content=header + combined, is_error=proc.returncode != 0)

    @staticmethod
    def _truncate(text: str, limit: int = 20000) -> str:
        if len(text) <= limit:
            return text
        keep = limit // 2
        return (
            text[:keep]
            + f"\n... [truncated {len(text) - limit} chars] ...\n"
            + text[-keep:]
        )
