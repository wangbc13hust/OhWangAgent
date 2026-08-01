from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_block(self) -> dict:
        return {
            "type": "tool_result",
            "content": self.content,
            "is_error": self.is_error,
        }


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    default_permission: str = "ask"

    @abstractmethod
    def execute(self, input: dict[str, Any]) -> ToolResult:
        ...

    def to_spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
