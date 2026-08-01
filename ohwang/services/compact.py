from __future__ import annotations

from typing import Iterator, Optional

from ..prompts import SUMMARY_PROMPT
from ..providers.base import BaseProvider
from .tokens import estimate_messages_tokens


def drain_text(stream: Iterator[dict]) -> str:
    parts: list[str] = []
    for event in stream:
        if event.get("type") == "text":
            parts.append(event["text"])
    return "".join(parts)


# Context-window-derived compaction thresholds, mirroring Claude Code's
# autoCompact.ts constants: compact when (window - output reserve) is about to
# be consumed, leaving the AUTOCOMPACT_BUFFER as headroom before a 413.
OUTPUT_RESERVE_TOKENS = 20_000
AUTOCOMPACT_BUFFER_TOKENS = 13_000
MIN_THRESHOLD_TOKENS = 4_000
DEFAULT_THRESHOLD_TOKENS = 100_000

# Substrings (lowercased) that identify a "prompt too long" / context-overflow
# API error across the supported providers (Anthropic, OpenAI-compatible,
# DeepSeek, Kimi, Qwen, Zhipu, ...).
_PTL_MARKERS = (
    "prompt is too long",
    "context length",
    "maximum context",
    "context_length_exceeded",
    "too many tokens",
    "input token count",
    "reduce the length",
)

_MICROCOMPACT_MARKER = "Old tool result content cleared"


def is_prompt_too_long_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _PTL_MARKERS)


def microcompact(messages: list[dict], max_tool_result_chars: int = 30_000) -> int:
    """Replace oversized tool results with a marker; return chars trimmed.

    Mirrors Claude Code's microCompact.ts: does NOT drop messages, only trims
    tool-result content that exceeds the size limit so a giant file read or
    command dump cannot silently bloat the context.
    """
    freed = 0
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            body = block.get("content", "")
            if not isinstance(body, str) or len(body) <= max_tool_result_chars:
                continue
            marker = f"[{_MICROCOMPACT_MARKER} (was {len(body)} chars)]"
            freed += len(body) - len(marker)
            block["content"] = marker
    return freed


class Compactor:
    """Summarizes older messages when the conversation exceeds a token budget."""

    def __init__(
        self,
        threshold_tokens: Optional[int] = None,
        keep_recent: int = 6,
        max_tokens: int = 1024,
        context_window: Optional[int] = None,
    ) -> None:
        if threshold_tokens is None:
            if context_window is not None:
                # Leave room for the response AND a buffer before the real
                # window (Claude Code: (window - 20k) - 13k).
                threshold_tokens = max(
                    MIN_THRESHOLD_TOKENS,
                    context_window
                    - OUTPUT_RESERVE_TOKENS
                    - AUTOCOMPACT_BUFFER_TOKENS,
                )
            else:
                threshold_tokens = DEFAULT_THRESHOLD_TOKENS
        self.threshold = threshold_tokens
        self.keep_recent = keep_recent
        self.max_tokens = max_tokens
        # Circuit breaker: stop paying for summarization calls that keep
        # failing; fall back to hard-trimming old messages instead
        # (Claude Code MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3).
        self.max_failures = 3
        self._consecutive_failures = 0

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
            return self._handle_failure(messages, recent)

        if not summary.strip():
            return self._handle_failure(messages, recent)

        self._consecutive_failures = 0
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

    def _handle_failure(
        self, messages: list[dict], recent: list[dict]
    ) -> list[dict]:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.max_failures:
            # Circuit breaker tripped: give up summarizing and hard-trim the
            # old span so the conversation can still move forward (snip).
            self._consecutive_failures = 0
            return recent
        return messages

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
