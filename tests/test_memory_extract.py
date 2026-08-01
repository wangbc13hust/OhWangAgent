from tests.helpers import ScriptedProvider, build_agent
from ohwang.services.memory import MemoryExtractor, MemoryStore


def test_parse_json_array():
    assert MemoryExtractor._parse(
        '[{"key": "a", "value": "b", "tags": ["x"]}]'
    ) == [{"key": "a", "value": "b", "tags": ["x"]}]


def test_parse_json_in_code_fence():
    payload = "```json\n[{\"key\": \"a\", \"value\": \"b\"}]\n```"
    assert MemoryExtractor._parse(payload) == [{"key": "a", "value": "b"}]


def test_parse_invalid_returns_empty():
    assert MemoryExtractor._parse("not json at all") == []
    assert MemoryExtractor._parse("") == []
    assert MemoryExtractor._parse("{}") == []


def test_extract_saves_facts(tmp_path):
    store = MemoryStore(str(tmp_path))
    provider = ScriptedProvider(
        [[{"type": "text", "text": '[{"key": "meeting_day", "value": "周会每周三", "tags": ["decision"]}]'}]]
    )
    ext = MemoryExtractor(store, growth_threshold=0)
    added = ext.extract(
        provider,
        [{"role": "user", "content": [{"type": "text", "text": "..."}]}],
    )
    assert added == 1
    assert store.get_fact("meeting_day") == "周会每周三"


def test_extract_bad_output_saves_nothing(tmp_path):
    store = MemoryStore(str(tmp_path))
    provider = ScriptedProvider([[{"type": "text", "text": "oops not json"}]])
    ext = MemoryExtractor(store, growth_threshold=0)
    assert ext.extract(provider, [{"role": "user", "content": "hi"}]) == 0
    assert store.list_facts() == []


def test_maybe_extract_respects_growth_threshold(tmp_path):
    store = MemoryStore(str(tmp_path))
    provider = ScriptedProvider([[{"type": "text", "text": "[]"}]])
    ext = MemoryExtractor(store, growth_threshold=10)
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "x"}]} for _ in range(5)
    ]
    assert ext.maybe_extract(provider, msgs) == 0
    msgs += [
        {"role": "user", "content": [{"type": "text", "text": "y"}]} for _ in range(10)
    ]
    assert ext.maybe_extract(provider, msgs) == 0  # runs, but no facts returned


def test_agent_auto_extract_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    responses = [
        [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "file_write",
                "input": {"file_path": "n.md", "content": "内容"},
            }
        ],
        [{"type": "text", "text": "done"}],
        [
            {
                "type": "text",
                "text": '[{"key": "style", "value": "用中文写文档", "tags": ["pref"]}]',
            }
        ],
    ]
    agent, provider = build_agent(responses)
    agent.run("写个文档")
    store = MemoryStore(str(tmp_path))
    ext = MemoryExtractor(store, growth_threshold=0)
    added = ext.extract(provider, agent.messages)
    assert added == 1
    assert store.get_fact("style") == "用中文写文档"
