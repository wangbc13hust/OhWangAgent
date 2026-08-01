from __future__ import annotations

from typing import Iterator

from ..prompts import SUMMARY_PROMPT
from ..providers.base import BaseProvider
from .tokens import estimate_messages_tokens


def drain_text(stream: Iterator[dict]) -> str:
    parts: list[str] = []
    for event in stream:
        if event.get("type") == "text":
            parts.append(event["text"])
    return "".join(parts)


class Compactor:
    """Summarizes older messages when the conversation exceeds a token budget."""

    def __init__(
        self,
        threshold_tokens: int = 100_000,
        keep_recent: int = 6,
        max_tokens: int = 1024,
    ) -> None:
        self.threshold = threshold_tokens
        self.keep_recent = keep_recent
        self.max_tokens = max_tokens

    def should_compact(self, messages: list[dict]) -> bool:
        return (
            estimate_messages_tokens(messages) > self.threshold
            and len(messages) > self.keep_recent + 2
        )

    def compact(
        self, messages: list[dict], provider: BaseProvider, system: str
    ) -> list[dict]:
        if len(messages) <= self.keep_recent:
            return messages

        old = messages[: -self.keep_recent]
        recent = messages[-self.keep_recent:]
        transcript = self._serialize(old)

        request = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Summarize the following conversation, preserving key "
                            "decisions, file paths, commands run, and pending tasks:\n\n"
                            + transcript
                        ),
                    }
                ],
            }
        ]

        try:
            summary = drain_text(
                provider.chat(
                    system=SUMMARY_PROMPT,
                    messages=request,
                    tools=[],
                    max_tokens=self.max_tokens,
                )
            )
        except Exception:
            return messages

        if not summary.strip():
            return messages

        summary_msg = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"[Summary of earlier conversation]\n{summary}",
                }
            ],
        }
        return [summary_msg] + recent

    @staticmethod
    def _serialize(messages: list[dict]) -> str:
        out: list[str] = []
        for m in messages:
            role = m["role"]
            content = m.get("content")
            if isinstance(content, str):
                out.append(f"{role}: {content}")
                continue
            if not isinstance(content, list):
                continue
            for b in content:
                btype = b.get("type")
                if btype == "text":
                    out.append(f"{role}: {b.get('text', '')}")
                elif btype == "tool_use":
                    out.append(
                        f"{role} [tool_use {b.get('name')}]: {b.get('input', {})}"
                    )
                elif btype == "tool_result":
                    out.append(f"{role} [tool_result]: {b.get('content', '')}")
        return "\n".join(out)
