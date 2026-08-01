from __future__ import annotations

from .base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._specs_cache: list[dict] | None = None

    def register(self, tool: BaseTool) -> "ToolRegistry":
        if not tool.name:
            raise ValueError("tool.name must be set")
        self._tools[tool.name] = tool
        self._specs_cache = None
        return self

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict]:
        if self._specs_cache is None:
            self._specs_cache = [t.to_spec() for t in self._tools.values()]
        return self._specs_cache

    def names(self) -> list[str]:
        return list(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
