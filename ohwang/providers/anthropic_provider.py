from __future__ import annotations

import json
from typing import Iterator

import anthropic

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Streams Anthropic Messages API and emits unified events.

    Internal message format is already Anthropic-style content blocks,
    so messages pass through unchanged.
    """

    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(api_key, model)
        self.client = anthropic.Anthropic(api_key=api_key, timeout=60)

    def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Iterator[dict]:
        kwargs = {
            "model": self.model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream_ctx = self.client.messages.stream(**kwargs)
            with stream_ctx as stream:
                current_tool: dict | None = None
                current_input_json = ""

                for event in stream:
                    etype = getattr(event, "type", None)

                    if etype == "content_block_start":
                        block = event.content_block
                        if getattr(block, "type", None) == "tool_use":
                            current_tool = {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": {},
                            }
                            current_input_json = ""

                    elif etype == "content_block_delta":
                        delta = event.delta
                        dtype = getattr(delta, "type", None)
                        if dtype == "text_delta":
                            yield {"type": "text", "text": delta.text}
                        elif dtype == "input_json_delta" and current_tool is not None:
                            current_input_json += delta.partial_json

                    elif etype == "content_block_stop":
                        if current_tool is not None:
                            try:
                                current_tool["input"] = json.loads(
                                    current_input_json or "{}"
                                )
                            except json.JSONDecodeError:
                                current_tool["input"] = {}
                            yield current_tool
                            current_tool = None
                            current_input_json = ""
        except Exception as exc:
            raise RuntimeError(
                f"API request failed (provider={self.name}, model={self.model}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc
