from __future__ import annotations

import os
import shutil
from typing import Callable, Optional

from .base import BaseTool, ToolResult
from .shell_output import command_result, stream_command


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

    def __init__(
        self,
        output_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        # Live stdout/stderr forwarding (name, text) for long-running commands;
        # the ToolResult content stays identical whether or not it is set.
        self._output_callback = output_callback

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
        stdout, stderr, returncode, timed_out = stream_command(
            cmd,
            shell=False,
            timeout=timeout,
            cwd=os.getcwd(),
            on_chunk=(lambda s, t: self._output_callback(s, t))
            if self._output_callback is not None
            else None,
        )
        if timed_out:
            return command_result("", "", 0, timed_out=True, timeout=timeout)
        return command_result(stdout, stderr, returncode)
