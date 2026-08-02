"""Dollar cost estimation (/cost) tests."""

from __future__ import annotations

from ohwang.cli import _cmd_cost
from ohwang.providers.base import BaseProvider
from ohwang.services.cost import calculate_cost, format_cost


def test_calculate_cost_known_model():
    cost = calculate_cost(1_000_000, 500_000, "deepseek", "deepseek-v4-flash")
    assert cost is not None
    assert round(cost, 6) == round(0.27 + 0.55, 6)  # 1M in @ .27 + 0.5M out @ 1.10


def test_calculate_cost_unknown_model_returns_none():
    assert calculate_cost(100, 50, "deepseek", "no-such-model") is None
    assert calculate_cost(100, 50, "no-such-provider", "deepseek-v4-flash") is None


def test_format_cost():
    assert format_cost(None) == "unknown"
    assert format_cost(0.0234) == "$0.0234"
    assert format_cost(0.000234) == "$0.000234"  # < $0.01 uses 6 decimals


class FakeProvider(BaseProvider):
    name = "fake"

    def chat(self, system, messages, tools, max_tokens):
        yield from ()


def _run_cmd_cost(provider, provider_name):
    captured = []
    warns = []

    class FakeAgent:
        pass

    FakeAgent.provider = provider

    class FakeRenderer:
        def info(self, s):
            captured.append(s)

        def warn(self, s):
            warns.append(s)

    class FakeConfig:
        provider = provider_name

    _cmd_cost(FakeAgent(), FakeRenderer(), FakeConfig())
    return captured, warns


def test_cmd_cost_renders_usage():
    provider = FakeProvider("k", "deepseek-v4-flash")
    provider._record_usage(1_000_000, 500_000)
    captured, warns = _run_cmd_cost(provider, "deepseek")
    assert any("Cost: $" in s for s in captured)
    assert any("Tokens:" in s for s in captured)
    assert "1000000 in / 500000 out" in " ".join(captured)
    assert not warns


def test_cmd_cost_unknown_model_warns():
    provider = FakeProvider("k", "no-such-model")
    provider._record_usage(100, 50)
    captured, warns = _run_cmd_cost(provider, "deepseek")
    assert any("Cost: unknown" in s for s in captured)
    assert any("No price for" in s for s in warns)


def test_cmd_cost_uses_current_model():
    # /model mutates agent.provider.model; cost must follow the live model.
    provider = FakeProvider("k", "deepseek-v4-flash")
    provider._record_usage(1_000_000, 0)
    provider.model = "deepseek-v4-pro"
    captured, _ = _run_cmd_cost(provider, "deepseek")
    assert "Cost: $0.5500" in captured
