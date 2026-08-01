from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class BaseProvider(ABC):
    name: str = ""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.usage_prompt_tokens: int = 0
        self.usage_completion_tokens: int = 0
        self.usage_calls: int = 0

    def _record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.usage_prompt_tokens += prompt_tokens
        self.usage_completion_tokens += completion_tokens
        self.usage_calls += 1

    def usage_report(self) -> dict:
        return {
            "calls": self.usage_calls,
            "prompt_tokens": self.usage_prompt_tokens,
            "completion_tokens": self.usage_completion_tokens,
            "total_tokens": self.usage_prompt_tokens + self.usage_completion_tokens,
        }

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
