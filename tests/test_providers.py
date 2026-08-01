import json
from types import SimpleNamespace

import pytest

from ohwang.config import Config
from ohwang.providers import create_provider
from ohwang.providers.anthropic_provider import AnthropicProvider
from ohwang.providers.openai_provider import OpenAIProvider, _convert_messages, _convert_tools


def test_convert_plain_string_message():
    out = _convert_messages([{"role": "user", "content": "hi"}])
    assert out == [{"role": "user", "content": "hi"}]


def test_convert_assistant_text_and_tool_calls():
    msgs = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "let me check"},
                {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}},
            ],
        }
    ]
    out = _convert_messages(msgs)
    assert len(out) == 1
    msg = out[0]
    assert msg["role"] == "assistant"
    assert msg["content"] == "let me check"
    tc = msg["tool_calls"][0]
    assert tc["id"] == "t1"
    assert tc["function"]["name"] == "bash"
    assert json.loads(tc["function"]["arguments"]) == {"command": "ls"}


def test_convert_assistant_tool_calls_only():
    msgs = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "grep", "input": {"pattern": "x"}}
            ],
        }
    ]
    out = _convert_messages(msgs)
    msg = out[0]
    assert msg["content"] is None
    assert msg["tool_calls"][0]["function"]["name"] == "grep"


def test_convert_user_tool_result_and_text():
    msgs = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": "output",
                    "is_error": False,
                },
                {"type": "text", "text": "continue"},
            ],
        }
    ]
    out = _convert_messages(msgs)
    assert out[0] == {"role": "tool", "tool_call_id": "t1", "content": "output"}
    assert out[1] == {"role": "user", "content": [{"type": "text", "text": "continue"}]}


def test_convert_skips_non_list_content():
    out = _convert_messages([{"role": "user", "content": None}])
    assert out == []


def test_convert_tools_wraps_schema():
    specs = [
        {
            "name": "bash",
            "description": "run",
            "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}},
        }
    ]
    out = _convert_tools(specs)
    assert out[0]["type"] == "function"
    f = out[0]["function"]
    assert f["name"] == "bash"
    assert f["description"] == "run"
    assert f["parameters"] == specs[0]["input_schema"]


def test_convert_tools_default_schema_when_missing():
    specs = [{"name": "x", "description": "", "input_schema": None}]
    out = _convert_tools(specs)
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


# ---------- create_provider ----------

def test_create_provider_anthropic(monkeypatch):
    from ohwang.providers import anthropic_provider
    monkeypatch.setattr(anthropic_provider.anthropic, "Anthropic", lambda **kw: object())
    cfg = Config(provider="anthropic", api_key="k", model="m").resolve()
    p = create_provider(cfg)
    assert isinstance(p, AnthropicProvider)
    assert p.model == "m"


def test_create_provider_openai_compatible(monkeypatch):
    from ohwang.providers import openai_provider
    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kw: object())
    for name in ("openai", "deepseek", "zhipu", "kimi", "qwen"):
        cfg = Config(provider=name, api_key="k", model="m").resolve()
        p = create_provider(cfg)
        assert isinstance(p, OpenAIProvider)
        assert p.model == "m"


def test_create_provider_passes_base_url(monkeypatch):
    from ohwang.providers import openai_provider
    captured = {}
    monkeypatch.setattr(openai_provider, "OpenAI", lambda **kw: captured.update(kw) or object())
    cfg = Config(provider="deepseek", api_key="k", model="m").resolve()
    create_provider(cfg)
    assert "base_url" in captured


def test_create_provider_unknown_raises():
    cfg = Config(provider="nope", api_key="k", model="m").resolve()
    with pytest.raises(ValueError):
        create_provider(cfg)


# ---------- OpenAIProvider.chat ----------

class _F:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, index, id=None, function=None):
        self.index = index
        self.id = id
        self.function = function


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, delta=None, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, choices):
        self.choices = choices


def _make_provider(monkeypatch, chunks):
    import ohwang.providers.openai_provider as mod
    captured = {}
    monkeypatch.setattr(mod, "OpenAI", lambda **kw: captured.setdefault("client", _FakeClient(chunks)) or captured["client"])
    return OpenAIProvider("k", "m"), captured["client"]


class _FakeClient:
    def __init__(self, chunks):
        self.chunks = chunks
        self.chat = _FakeChat(chunks)


class _FakeChat:
    def __init__(self, chunks):
        self.completions = _FakeCompletions(chunks)


class _FakeCompletions:
    def __init__(self, chunks):
        self.chunks = chunks
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return iter(self.chunks)


def test_openai_chat_streams_text_and_tool_call(monkeypatch):
    chunks = [
        _Chunk([_Choice(delta=_Delta(content="Hel"), finish_reason=None)]),
        _Chunk([_Choice(delta=_Delta(content="lo"), finish_reason=None)]),
        _Chunk([_Choice(delta=_Delta(tool_calls=[_TC(0, id="tc1", function=_F("bash", '{"cmd":'))]), finish_reason=None)]),
        _Chunk([_Choice(delta=_Delta(tool_calls=[_TC(0, function=_F(None, ' "ls"}'))]), finish_reason=None)]),
        _Chunk([_Choice(delta=_Delta(), finish_reason="tool_calls")]),
    ]
    p, client = _make_provider(monkeypatch, chunks)
    events = list(p.chat("sys", [{"role": "user", "content": "hi"}], [], 100))
    texts = [e["text"] for e in events if e["type"] == "text"]
    tools = [e for e in events if e["type"] == "tool_use"]
    assert "".join(texts) == "Hello"
    assert len(tools) == 1
    assert tools[0]["id"] == "tc1"
    assert tools[0]["name"] == "bash"
    assert tools[0]["input"] == {"cmd": "ls"}


def test_openai_chat_skips_empty_choices_and_parses_bad_json(monkeypatch):
    chunks = [
        _Chunk([]),
        _Chunk([_Choice(delta=_Delta(tool_calls=[_TC(0, id="t", function=_F("bash", "{bad json"))]), finish_reason="tool_calls")]),
    ]
    p, client = _make_provider(monkeypatch, chunks)
    events = list(p.chat("sys", [], [], 100))
    tool = events[0]
    assert tool["input"] == {}


def test_openai_chat_sends_tools(monkeypatch):
    p, client = _make_provider(monkeypatch, [_Chunk([_Choice(delta=_Delta(content="ok"), finish_reason="stop")])])
    specs = [{"name": "bash", "description": "run", "input_schema": {"type": "object"}}]
    list(p.chat("sys", [{"role": "user", "content": "hi"}], specs, 100))
    kwargs = client.chat.completions.create_calls[0]
    assert kwargs["tools"][0]["type"] == "function"


def test_openai_chat_wraps_api_error(monkeypatch):
    import ohwang.providers.openai_provider as mod

    class BoomCompletions:
        def create(self, **kwargs):
            raise ValueError("network down")

    class BoomClient:
        chat = SimpleNamespace(completions=BoomCompletions())

    monkeypatch.setattr(mod, "OpenAI", lambda **kw: BoomClient())
    p = OpenAIProvider("k", "m")
    with pytest.raises(RuntimeError, match="API request failed"):
        list(p.chat("sys", [], [], 100))


# ---------- AnthropicProvider.chat ----------

def test_anthropic_chat_streams_text_and_tool(monkeypatch):
    import ohwang.providers.anthropic_provider as mod

    class _CB:
        type = "content_block_start"

        def __init__(self, block):
            self.content_block = block

    class _CD:
        type = "content_block_delta"

        def __init__(self, delta):
            self.delta = delta

    class _CBS:
        type = "content_block_stop"

    class _Block:
        def __init__(self, btype, id=None, name=None):
            self.type = btype
            self.id = id
            self.name = name

    class _Delta:
        def __init__(self, dtype, text=None, partial_json=None):
            self.type = dtype
            self.text = text
            self.partial_json = partial_json

    events = [
        _CD(delta=_Delta("text_delta", text="hi")),
        _CB(block=_Block("tool_use", id="t1", name="bash")),
        _CD(delta=_Delta("input_json_delta", partial_json='{"a"')),
        _CD(delta=_Delta("input_json_delta", partial_json=":1}")),
        _CBS(),
    ]

    class _Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def __iter__(self):
            return iter(events)

    class _Ctx:
        def stream(self, **kwargs):
            return _Stream()

    class _FakeAnthropic:
        def __init__(self, **kw):
            self.messages = _Ctx()

    monkeypatch.setattr(mod.anthropic, "Anthropic", _FakeAnthropic)
    p = AnthropicProvider("k", "m")
    out = list(p.chat("sys", [], [], 100))
    texts = [e["text"] for e in out if e["type"] == "text"]
    tools = [e for e in out if e["type"] == "tool_use"]
    assert texts == ["hi"]
    assert tools[0]["id"] == "t1"
    assert tools[0]["input"] == {"a": 1}


def test_anthropic_chat_handles_bad_tool_json(monkeypatch):
    import ohwang.providers.anthropic_provider as mod

    class _CB:
        type = "content_block_start"

        def __init__(self, block):
            self.content_block = block

    class _CD:
        type = "content_block_delta"

        def __init__(self, delta):
            self.delta = delta

    class _CBS:
        type = "content_block_stop"

    class _Block:
        type = "tool_use"

        def __init__(self, id, name):
            self.id = id
            self.name = name

    class _Delta:
        type = "input_json_delta"

        def __init__(self, partial_json):
            self.partial_json = partial_json

    events = [
        _CB(block=_Block("t1", "bash")),
        _CD(delta=_Delta("{oops")),
        _CBS(),
    ]

    class _Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def __iter__(self):
            return iter(events)

    class _FakeAnthropic:
        def __init__(self, **kw):
            self.messages = type("M", (), {"stream": lambda self, **k: _Stream()})()

    monkeypatch.setattr(mod.anthropic, "Anthropic", _FakeAnthropic)
    p = AnthropicProvider("k", "m")
    out = list(p.chat("sys", [], [], 100))
    assert out[0]["input"] == {}


def test_anthropic_chat_wraps_api_error(monkeypatch):
    import ohwang.providers.anthropic_provider as mod

    class _BoomMessages:
        def stream(self, **kwargs):
            raise OSError("boom")

    class _FakeAnthropic:
        def __init__(self, **kw):
            self.messages = _BoomMessages()

    monkeypatch.setattr(mod.anthropic, "Anthropic", _FakeAnthropic)
    p = AnthropicProvider("k", "m")
    with pytest.raises(RuntimeError, match="API request failed"):
        list(p.chat("sys", [], [], 100))


def test_provider_usage_accumulates():
    from ohwang.providers.base import BaseProvider

    class P(BaseProvider):
        name = "p"

        def chat(self, system, messages, tools, max_tokens):
            yield from ()

    p = P("k", "m")
    p._record_usage(100, 20)
    p._record_usage(50, 30)
    rep = p.usage_report()
    assert rep["calls"] == 2
    assert rep["prompt_tokens"] == 150
    assert rep["completion_tokens"] == 50
    assert rep["total_tokens"] == 200


def test_openai_provider_records_usage_from_chunks():
    from ohwang.providers.openai_provider import OpenAIProvider

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5

    class _Chunk:
        def __init__(self, usage=None, choices=None):
            self.usage = usage
            self.choices = choices or []

    chunks = [_Chunk(usage=_Usage())]

    class _Stream:
        def __init__(self):
            self._i = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self._i >= len(chunks):
                raise StopIteration
            c = chunks[self._i]
            self._i += 1
            return c

    class _Completions:
        def create(self, **kw):
            return _Stream()

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class _FakeClient:
        def __init__(self, **kw):
            self.chat = _Chat()

    import ohwang.providers.openai_provider as mod

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mod.OpenAI, "__new__", lambda cls, *a, **kw: _FakeClient())
    p = OpenAIProvider("k", "m")
    list(p.chat("sys", [], [], 10))
    rep = p.usage_report()
    assert rep["calls"] == 1
    assert rep["prompt_tokens"] == 10
    assert rep["completion_tokens"] == 5
    monkeypatch.undo()


def test_anthropic_provider_records_usage(monkeypatch):
    import ohwang.providers.anthropic_provider as mod

    class _InUsage:
        input_tokens = 11

    class _OutUsage:
        output_tokens = 7

    class _Message:
        usage = _InUsage()

    class _MS:
        type = "message_start"
        message = _Message()

    class _MD:
        type = "message_delta"
        usage = _OutUsage()

    events = [_MS(), _MD()]

    class _Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def __iter__(self):
            return iter(events)

    class _FakeAnthropic:
        def __init__(self, **kw):
            self.messages = type("M", (), {"stream": lambda self, **k: _Stream()})()

    monkeypatch.setattr(mod.anthropic, "Anthropic", _FakeAnthropic)
    p = AnthropicProvider("k", "m")
    list(p.chat("sys", [], [], 100))
    rep = p.usage_report()
    assert rep["calls"] == 1
    assert rep["prompt_tokens"] == 11
    assert rep["completion_tokens"] == 7


def _capture_fake_anthropic(captured, monkeypatch):
    import ohwang.providers.anthropic_provider as mod

    class _Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def __iter__(self):
            return iter([])

    class _Ctx:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return _Stream()

    class _FakeAnthropic:
        def __init__(self, **kw):
            self.messages = _Ctx()

    monkeypatch.setattr(mod.anthropic, "Anthropic", _FakeAnthropic)
    return AnthropicProvider("k", "m")


def test_anthropic_system_blocks_with_cache_control(monkeypatch):
    monkeypatch.delenv("DISABLE_PROMPT_CACHING", raising=False)
    captured: dict = {}
    p = _capture_fake_anthropic(captured, monkeypatch)

    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    list(p.chat("sys", msgs, [], 100))

    system = captured["system"]
    assert isinstance(system, list)
    assert system[0]["text"] == "sys"
    assert system[0]["cache_control"] == {"type": "ephemeral"}

    sent = captured["messages"]
    assert sent[-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    # caller's dicts are not mutated by the breakpoint copy
    assert "cache_control" not in msgs[0]["content"][0]
    assert sent is not msgs


def test_anthropic_caching_disabled_env(monkeypatch):
    monkeypatch.setenv("DISABLE_PROMPT_CACHING", "1")
    captured: dict = {}
    p = _capture_fake_anthropic(captured, monkeypatch)

    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    list(p.chat("sys", msgs, [], 100))

    assert captured["system"] == "sys"          # plain string, no blocks
    assert captured["messages"] is msgs          # untouched, no breakpoint
    assert "cache_control" not in captured["messages"][0]["content"][0]
