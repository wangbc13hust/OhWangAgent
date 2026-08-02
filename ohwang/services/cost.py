"""Dollar cost estimation for a session.

Multiplies the token counts already recorded by the provider
(BaseProvider.usage_prompt_tokens / usage_completion_tokens, exposed via
usage_report()) by a static per-(provider, model) price table in USD per 1M
tokens. Prices are best-effort values from public pricing pages; edit
PRICE_TABLE to tune. Unknown (provider, model) combos return None so the CLI
can render "unknown" instead of crashing.
"""

from __future__ import annotations

# key = (provider, model); value = USD per 1M tokens for prompt / completion.
PRICE_TABLE: dict[tuple[str, str], dict[str, float]] = {
    ("anthropic", "claude-sonnet-4-5-20250929"): {"in": 3.00, "out": 15.00},
    ("openai", "gpt-4o"): {"in": 2.50, "out": 10.00},
    ("deepseek", "deepseek-v4-flash"): {"in": 0.27, "out": 1.10},
    ("deepseek", "deepseek-v4-pro"): {"in": 0.55, "out": 2.19},
    ("zhipu", "glm-5.2"): {"in": 0.60, "out": 2.00},
    ("kimi", "moonshot-v1-8k"): {"in": 1.20, "out": 6.00},
    ("qwen", "qwen-max"): {"in": 1.60, "out": 6.40},
}


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    provider: str,
    model: str,
) -> float | None:
    """USD cost for the given token counts, or None if the model is unpriced."""
    price = PRICE_TABLE.get((provider, model))
    if price is None:
        return None
    return (prompt_tokens / 1_000_000) * price["in"] + (
        completion_tokens / 1_000_000
    ) * price["out"]


def format_cost(cost: float | None) -> str:
    """Render a cost as a $-string, or "unknown" when unpriced."""
    if cost is None:
        return "unknown"
    if cost < 0.01:
        return f"${cost:.6f}"
    return f"${cost:.4f}"
