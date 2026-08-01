from __future__ import annotations

import json
import os
from typing import Iterator

import anthropic

from .base import BaseProvider


def _cache_enabled() -> bool:
    # Prompt caching is on by default for Anthropic; set DISABLE_PROMPT_CACHING
    # to opt out (mirrors Claude Code's per-model DISABLE_PROMPT_CACHING_* envs).
    return not os.environ.get("DISABLE_PROMPT_CACHING")


def _system_blocks(system: str) -> list[dict]:
    """Build the system argument as a cacheable text block (Anthropic SDK
    accepts a str OR a list of blocks; the latter lets us attach cache_control).
    """
    return [
        {
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _with_cache_breakpoint(messages: list[dict]) -> list[dict]:
    """Return messages with cache_control on the last content block of the
    last message, without mutating the caller's dicts. Mirrors Claude Code's
    addCacheBreakpoints(): one breakpoint per request so the whole prefix up to
    the final message is cached.
    """
    if not messages:
        return messages
    last = messages[-1]
    content = last.get("content")
    if not isinstance(content, list) or not content:
        return messages
    copied = dict(last)
    blocks = list(content)
    copied["content"] = blocks
    blocks[-1] = dict(blocks[-1])
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return messages[:-1] + [copied]


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
        caching = _cache_enabled()
        kwargs = {
            "model": self.model,
            "system": _system_blocks(system) if caching else system,
            "messages": _with_cache_breakpoint(messages) if caching else messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream_ctx = self.client.messages.stream(**kwargs)
            with stream_ctx as stream:
                current_tool: dict | None = None
                current_input_json = ""
                input_tokens = 0

                for event in stream:
                    etype = getattr(event, "type", None)

                    if etype == "message_start":
                        usage = getattr(getattr(event, "message", None), "usage", None)
                        if usage is not None:
                            input_tokens = getattr(usage, "input_tokens", 0) or 0

                    elif etype == "message_delta":
                        usage = getattr(event, "usage", None)
                        if usage is not None:
                            self._record_usage(
                                input_tokens, getattr(usage, "output_tokens", 0) or 0
                            )

                    elif etype == "content_block_start":
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
