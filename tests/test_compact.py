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
