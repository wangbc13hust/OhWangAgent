from ohwang.services.compact import Compactor
from tests.helpers import ScriptedProvider


def test_should_compact_below_threshold():
    c = Compactor(threshold_tokens=100_000)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "short"}]}]
    assert not c.should_compact(msgs)


def test_compact_summarizes_old_messages():
    c = Compactor(threshold_tokens=1, keep_recent=2, max_tokens=64)
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "old message one"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "old reply one"}]},
        {"role": "user", "content": [{"type": "text", "text": "recent one"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "recent reply"}]},
    ]
    provider = ScriptedProvider([[{"type": "text", "text": "SUMMARY: did stuff"}]])
    result = c.compact(msgs, provider, "system")

    assert len(result) == 3
    assert "SUMMARY" in result[0]["content"][0]["text"]
    assert result[1] == msgs[2]
    assert result[2] == msgs[3]
    assert provider.i == 1


def test_compact_keeps_all_when_few_messages():
    c = Compactor(threshold_tokens=1, keep_recent=10)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    provider = ScriptedProvider([])
    assert c.compact(msgs, provider, "system") is msgs


def test_compact_falls_back_on_provider_error():
    c = Compactor(threshold_tokens=1, keep_recent=2)

    class BoomProvider(ScriptedProvider):
        def chat(self, *a, **k):
            raise RuntimeError("boom")
            yield  # noqa

    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "a"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "b"}]},
        {"role": "user", "content": [{"type": "text", "text": "c"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "d"}]},
    ]
    result = c.compact(msgs, BoomProvider([]), "system")
    assert result is msgs


def test_compactor_derives_threshold_from_window():
    c = Compactor(threshold_tokens=None, context_window=64_000)
    assert c.threshold == 64_000 - 20_000 - 13_000


def test_compactor_window_clamp_floor():
    # tiny window (kimi-8k) -> clamped to the minimum threshold
    c = Compactor(threshold_tokens=None, context_window=8_192)
    assert c.threshold == 4_000


def test_compactor_no_window_falls_back_to_default():
    c = Compactor(threshold_tokens=None, context_window=None)
    assert c.threshold == 100_000


def test_compactor_circuit_breaker_hard_trims():
    c = Compactor(threshold_tokens=1, keep_recent=2, max_tokens=64)

    class BoomProvider(ScriptedProvider):
        def chat(self, *a, **k):
            raise RuntimeError("boom")
            yield  # noqa

    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "a"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "b"}]},
        {"role": "user", "content": [{"type": "text", "text": "c"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "d"}]},
    ]
    provider = BoomProvider([])

    first = c.compact(msgs, provider, "system")
    assert first is msgs            # first failure: unchanged
    second = c.compact(msgs, provider, "system")
    assert second is msgs           # second failure: still unchanged
    third = c.compact(msgs, provider, "system")
    assert len(third) == c.keep_recent
    assert third[0] is msgs[-2]     # hard-trim kept the recent span
    assert third[1] is msgs[-1]


def test_compactor_resets_breaker_on_success():
    c = Compactor(threshold_tokens=1, keep_recent=2, max_tokens=64)

    class Flaky(ScriptedProvider):
        def __init__(self):
            super().__init__([[{"type": "text", "text": "SUMMARY"}]])
            self.n = 0

        def chat(self, *a, **k):
            self.n += 1
            if self.n <= 2:
                raise RuntimeError("boom")
                yield  # noqa
            yield from super().chat(*a, **k)

    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "a"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "b"}]},
        {"role": "user", "content": [{"type": "text", "text": "c"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "d"}]},
    ]
    p = Flaky()
    c.compact(msgs, p, "system")    # failure 1 -> unchanged
    c.compact(msgs, p, "system")    # failure 2 -> unchanged
    result = c.compact(msgs, p, "system")   # success resets the counter
    assert result is not msgs
    assert "SUMMARY" in result[0]["content"][0]["text"]


def test_is_prompt_too_long_error_matches():
    from ohwang.services.compact import is_prompt_too_long_error

    assert is_prompt_too_long_error(
        RuntimeError("API request failed: prompt is too long (max 200000)")
    )
    assert is_prompt_too_long_error(
        RuntimeError("This model's maximum context length is 128000 tokens")
    )
    assert is_prompt_too_long_error(
        RuntimeError("Invalid input. Input token count (12345) exceeds max tokens")
    )
    assert not is_prompt_too_long_error(RuntimeError("boom"))
    assert not is_prompt_too_long_error(
        RuntimeError("API request failed: rate limit exceeded")
    )
