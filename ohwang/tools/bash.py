from __future__ import annotations

import os
from typing import Callable, Optional

from .base import BaseTool, ToolResult
from .shell_output import command_result, stream_command


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

        stdout, stderr, returncode, timed_out = stream_command(
            command,
            shell=True,
            timeout=timeout,
            cwd=os.getcwd(),
            on_chunk=(lambda s, t: self._output_callback(s, t))
            if self._output_callback is not None
            else None,
        )
        if timed_out:
            return command_result("", "", 0, timed_out=True, timeout=timeout)
        return command_result(stdout, stderr, returncode)
