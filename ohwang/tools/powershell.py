from __future__ import annotations

import os
import shutil
import subprocess

from .base import BaseTool, ToolResult
from .shell_output import command_result, decode_output


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
                timeout=timeout,
                cwd=os.getcwd(),
            )
        except subprocess.TimeoutExpired:
            return command_result("", "", 0, timed_out=True, timeout=timeout)

        return command_result(
            decode_output(proc.stdout or b""),
            decode_output(proc.stderr or b""),
            proc.returncode,
        )
