from __future__ import annotations

from .base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> "ToolRegistry":
        if not tool.name:
            raise ValueError("tool.name must be set")
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict]:
        return [t.to_spec() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
