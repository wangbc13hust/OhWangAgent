from __future__ import annotations

import os
import subprocess

from .base import BaseTool, ToolResult
from .shell_output import command_result, decode_output


class BashTool(BaseTool):
    name = "bash"
    description = (
        "Execute a shell command and return stdout+stderr. Use this to run "
        "builds, tests, git, and inspect the system. On Windows it runs via cmd."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
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

        try:
            proc = subprocess.run(
                command,
                shell=True,
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
