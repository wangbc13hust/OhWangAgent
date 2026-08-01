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


def test_maybe_extract_does_not_advance_on_provider_error(tmp_path):
    store = MemoryStore(str(tmp_path))
    ext = MemoryExtractor(store, growth_threshold=0)

    class BoomProvider:
        def chat(self, *a, **k):
            raise RuntimeError("network down")
            yield  # noqa

    msgs = [{"role": "user", "content": [{"type": "text", "text": "x"}]}]
    assert ext.maybe_extract(BoomProvider(), msgs) == 0
    # failure must NOT advance the counter, or a transient network error would
    # permanently skip extraction for the rest of the session.
    assert ext._last_count == 0


def test_extract_routes_user_type_to_user_layer(tmp_path):
    store = MemoryStore(str(tmp_path), home_dir=str(tmp_path / "home"))
    provider = ScriptedProvider(
        [
            [
                {
                    "type": "text",
                    "text": (
                        '[{"key": "pref", "value": "prefers Chinese", "tags": ["pref"], "type": "user"},'
                        '{"key": "arch", "value": "uses JWT", "tags": ["decision"], "type": "project"}]'
                    ),
                }
            ]
        ]
    )
    ext = MemoryExtractor(store, growth_threshold=0)
    added = ext.extract(
        provider, [{"role": "user", "content": [{"type": "text", "text": "..."}]}]
    )
    assert added == 2
    assert store.get_fact("pref", scope="user") == "prefers Chinese"
    assert store.get_fact("pref") is None
    assert store.get_fact("arch") == "uses JWT"


def test_extract_user_falls_back_when_no_home_dir(tmp_path):
    store = MemoryStore(str(tmp_path))
    provider = ScriptedProvider(
        [
            [
                {
                    "type": "text",
                    "text": '[{"key": "pref", "value": "prefers Chinese", "type": "user"}]',
                }
            ]
        ]
    )
    ext = MemoryExtractor(store, growth_threshold=0)
    assert ext.extract(
        provider, [{"role": "user", "content": [{"type": "text", "text": "..."}]}]
    ) == 1
    assert store.get_fact("pref") == "prefers Chinese"  # landed in project layer


def test_extract_cursor_persists_across_instances(tmp_path):
    store = MemoryStore(str(tmp_path))
    ext1 = MemoryExtractor(store, growth_threshold=10)
    provider = ScriptedProvider([[{"type": "text", "text": "[]"}]])
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "x"}]} for _ in range(10)
    ]
    assert ext1.maybe_extract(provider, msgs) == 0
    assert ext1._last_count == 10
    ext2 = MemoryExtractor(store, growth_threshold=10)
    assert ext2._last_count == 10  # loaded from extract_cursor.json
    # below threshold again -> no re-extraction of already-seen history
    assert ext2.maybe_extract(provider, msgs) == 0


def test_extract_missing_type_defaults_project(tmp_path):
    store = MemoryStore(str(tmp_path), home_dir=str(tmp_path / "home"))
    provider = ScriptedProvider(
        [
            [
                {
                    "type": "text",
                    "text": '[{"key": "old", "value": "legacy fact", "tags": []}]',
                }
            ]
        ]
    )
    ext = MemoryExtractor(store, growth_threshold=0)
    assert ext.extract(
        provider, [{"role": "user", "content": [{"type": "text", "text": "..."}]}]
    ) == 1
    assert store.get_fact("old") == "legacy fact"  # project layer despite home_dir
    assert store.list_facts(scope="user") == []


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
