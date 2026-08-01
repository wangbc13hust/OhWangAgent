from __future__ import annotations

import json
from typing import Iterator

from openai import OpenAI

from .base import BaseProvider


def _convert_tools(tools: list[dict]) -> list[dict]:
    out = []
    for t in tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema") or {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
        )
    return out


def _convert_messages(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        role = m["role"]
        content = m.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            continue

        if role == "assistant":
            text = "".join(
                b.get("text", "") for b in content if b.get("type") == "text"
            )
            tool_calls = []
            for b in content:
                if b.get("type") == "tool_use":
                    tool_calls.append(
                        {
                            "id": b["id"],
                            "type": "function",
                            "function": {
                                "name": b["name"],
                                "arguments": json.dumps(
                                    b.get("input", {}), ensure_ascii=False
                                ),
                            },
                        }
                    )
            msg: dict = {"role": "assistant", "content": text or None}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            out.append(msg)

        elif role == "user":
            text_blocks = [
                {"type": "text", "text": b["text"]}
                for b in content
                if b.get("type") == "text"
            ]
            for b in content:
                if b.get("type") == "tool_result":
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": b["tool_use_id"],
                            "content": b.get("content", ""),
                        }
                    )
            if text_blocks:
                out.append({"role": "user", "content": text_blocks})

    return out


class OpenAIProvider(BaseProvider):
    """Streams an OpenAI-compatible Chat Completions API and emits unified events.

    Works with OpenAI itself and any compatible endpoint (DeepSeek, Kimi,
    Qwen, local vLLM, etc.) by setting base_url on the client.
    """

    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        super().__init__(api_key, model)
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(timeout=60, max_retries=2, **client_kwargs)

    def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Iterator[dict]:
        openai_messages = [{"role": "system", "content": system}]
        openai_messages.extend(_convert_messages(messages))

        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = _convert_tools(tools)

        try:
            stream = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"API request failed (provider={self.name}, model={self.model}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        tool_acc: dict[int, dict] = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if delta and delta.content:
                yield {"type": "text", "text": delta.content}

            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    entry = tool_acc.setdefault(
                        idx,
                        {
                            "type": "tool_use",
                            "id": "",
                            "name": "",
                            "input_raw": "",
                        },
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function.arguments:
                            entry["input_raw"] += tc.function.arguments

            if choice.finish_reason:
                for idx in sorted(tool_acc):
                    entry = tool_acc[idx]
                    raw = entry.pop("input_raw", "")
                    try:
                        entry["input"] = json.loads(raw) if raw.strip() else {}
                    except json.JSONDecodeError:
                        entry["input"] = {}
                    yield entry
                break
