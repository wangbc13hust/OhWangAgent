from __future__ import annotations

import threading

# Heuristic fallback constants — used only when tiktoken is unavailable or its
# encoding cannot be loaded (e.g. offline before the first BPE download).
CHARS_PER_TOKEN = 4
_PER_MESSAGE_OVERHEAD = 4
_PER_BLOCK_OVERHEAD = 8

try:
    import tiktoken as _tiktoken
except Exception:  # pragma: no cover - offline install guard
    _tiktoken = None

_ENC_CACHE: dict[str, object] = {}
_ENC_LOCK = threading.Lock()
# cl100k_base is a good approximation for models without a published OpenAI
# encoding (DeepSeek recommends it for its tokenizer, and it fits the other
# domestic providers reasonably well).
_FALLBACK_ENCODING = "cl100k_base"


def _get_encoding(model: str | None) -> object | None:
    """Return a cached tiktoken encoding for `model`, or None on any failure."""
    if _tiktoken is None:
        return None
    try:
        name = _encoding_name(model)
    except Exception:
        return None
    enc = _ENC_CACHE.get(name)
    if enc is not None:
        return enc
    with _ENC_LOCK:
        enc = _ENC_CACHE.get(name)
        if enc is None:
            enc = _tiktoken.get_encoding(name)
            _ENC_CACHE[name] = enc
    return enc


def _encoding_name(model: str | None) -> str:
    if not model:
        return _FALLBACK_ENCODING
    try:
        return _tiktoken.encoding_for_model(model).name
    except Exception:
        return _FALLBACK_ENCODING


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _heuristic_text_tokens(text: str) -> int:
    if not text:
        return 0
    # CJK text is far denser than ~4 chars/token; ~1 char/token keeps the
    # compaction trigger from massively under-estimating Chinese prompts.
    if _has_cjk(text):
        return max(1, len(text))
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_text_tokens(text: str, model: str | None = None) -> int:
    """Exact tokenizer count when available; ~4 chars/token heuristic otherwise."""
    if not text:
        return 0
    enc = _get_encoding(model)
    if enc is not None:
        try:
            return max(1, len(enc.encode(text)))
        except Exception:
            pass
    return _heuristic_text_tokens(text)


def estimate_messages_tokens(messages: list[dict], model: str | None = None) -> int:
    """Estimate tokens for a message list.

    Uses tiktoken (the model's encoding, or cl100k_base) when it is available
    and falls back to the ~4 chars/token heuristic otherwise — so callers keep
    working offline or before the first BPE download. Per-message and
    per-block overhead constants are retained in both paths.
    """
    total = 0
    for m in messages:
        total += _PER_MESSAGE_OVERHEAD
        content = m.get("content")
        if isinstance(content, str):
            total += estimate_text_tokens(content, model)
            continue
        if not isinstance(content, list):
            continue
        for b in content:
            btype = b.get("type")
            if btype == "text":
                total += (
                    estimate_text_tokens(b.get("text", ""), model) + _PER_BLOCK_OVERHEAD
                )
            elif btype == "tool_use":
                total += (
                    estimate_text_tokens(b.get("name", ""), model) + _PER_BLOCK_OVERHEAD
                )
                total += (
                    estimate_text_tokens(str(b.get("input", {})), model)
                    + _PER_BLOCK_OVERHEAD
                )
            elif btype == "tool_result":
                total += (
                    estimate_text_tokens(str(b.get("content", "")), model)
                    + _PER_BLOCK_OVERHEAD
                )
    return total
