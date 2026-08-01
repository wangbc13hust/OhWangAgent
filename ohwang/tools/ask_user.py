from __future__ import annotations

from typing import Callable, Optional

from .base import BaseTool, ToolResult


AskQuestionCallback = Callable[[str, list], str]


class AskUserQuestionTool(BaseTool):
    name = "ask_user_question"
    description = (
        "Ask the user a clarifying question with a list of options. "
        "Use when you need a decision or preference before proceeding."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "header": {"type": "string", "description": "Short label (<=30 chars)."},
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["label"],
                },
            },
        },
        "required": ["question", "header", "options"],
    }
    default_permission = "allow"

    def __init__(self, callback: Optional[AskQuestionCallback] = None) -> None:
        self._callback = callback

    def execute(self, input: dict) -> ToolResult:
        if self._callback is None:
            return ToolResult(
                content="Unable to ask user (non-interactive mode). "
                "Proceed with the most reasonable default."
            )
        question = input["question"]
        options = input.get("options", [])
        answer = self._callback(question, options)
        return ToolResult(content=f"User selected: {answer}")
