from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class BaseProvider(ABC):
    name: str = ""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Iterator[dict]:
        """Stream a completion.

        Yields unified events:
          {"type": "text", "text": "..."}            # incremental text
          {"type": "tool_use", "id": ..., "name": ..., "input": {...}}
          {"type": "stop", "reason": "end_turn" | "tool_use"}
        """
        ...
