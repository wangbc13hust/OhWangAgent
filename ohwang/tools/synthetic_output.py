from __future__ import annotations

from .base import BaseTool, ToolResult


class SyntheticOutputTool(BaseTool):
    name = "synthetic_output"
    description = (
        "Show a piece of text to the user in the terminal WITHOUT adding it to the "
        "model context. Use for progress messages, confirmations, or large outputs "
        "that should not be re-sent to the model."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to display to the user.",
            }
        },
        "required": ["text"],
    }
    default_permission = "allow"

    def __init__(self, display=None) -> None:
        self._display = display

    def execute(self, input: dict) -> ToolResult:
        text = input.get("text", "")
        if self._display is not None:
            self._display(text)
        return ToolResult(content="(shown to user)")
