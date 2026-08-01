from __future__ import annotations

CHARS_PER_TOKEN = 4
_PER_MESSAGE_OVERHEAD = 4
_PER_BLOCK_OVERHEAD = 8


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    # CJK text is far denser than ~4 chars/token; counting ~1 char/token keeps
    # the compaction trigger from massively under-estimating Chinese prompts.
    if _has_cjk(text):
        return max(1, len(text))
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Rough local token estimate (~4 chars/token) with per-block overhead.

    Good enough for compaction triggers; not an exact tokenizer.
    """
    total = 0
    for m in messages:
        total += _PER_MESSAGE_OVERHEAD
        content = m.get("content")
        if isinstance(content, str):
            total += estimate_text_tokens(content)
            continue
        if not isinstance(content, list):
            continue
        for b in content:
            btype = b.get("type")
            if btype == "text":
                total += estimate_text_tokens(b.get("text", "")) + _PER_BLOCK_OVERHEAD
            elif btype == "tool_use":
                total += estimate_text_tokens(b.get("name", "")) + _PER_BLOCK_OVERHEAD
                total += estimate_text_tokens(str(b.get("input", {}))) + _PER_BLOCK_OVERHEAD
            elif btype == "tool_result":
                total += estimate_text_tokens(str(b.get("content", ""))) + _PER_BLOCK_OVERHEAD
    return total
