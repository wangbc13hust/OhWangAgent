from __future__ import annotations

from typing import Callable

from .base import BaseTool, ToolResult


class AgentTool(BaseTool):
    name = "agent"
    description = (
        "Spawn a sub-agent with an isolated context to work on a subtask. "
        "Returns the sub-agent's final answer. Use for delegation or focused "
        "research that doesn't need to pollute the main context."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Short (3-5 word) label."},
            "prompt": {"type": "string", "description": "The task for the sub-agent."},
        },
        "required": ["description", "prompt"],
    }
    default_permission = "allow"

    def __init__(self, factory: Callable[[], "object"]) -> None:
        self._factory = factory

    def execute(self, input: dict) -> ToolResult:
        prompt = input["prompt"]
        sub = self._factory()
        try:
            result = sub.run(prompt)
        except Exception as exc:
            return ToolResult(content=f"Sub-agent failed: {exc}", is_error=True)
        return ToolResult(content=result or "(sub-agent produced no output)")
