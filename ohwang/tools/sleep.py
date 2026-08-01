from __future__ import annotations

import time

from .base import BaseTool, ToolResult


class SleepTool(BaseTool):
    name = "sleep"
    description = (
        "Wait for the given number of seconds, then return. Use for pacing, "
        "waiting on external processes, or timed operations."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "integer",
                "description": "Seconds to wait (1-3600).",
            }
        },
        "required": ["seconds"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        seconds = self._clamp(input.get("seconds", 1))
        time.sleep(seconds)
        return ToolResult(content=f"Slept {seconds}s.")

    @staticmethod
    def _clamp(seconds) -> int:
        return max(1, min(int(seconds), 3600))
