import tempfile

from ohwang.services.session import SessionStore


def test_save_load_roundtrip():
    d = tempfile.mkdtemp()
    s = SessionStore(d)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    sid = s.save(msgs, preview="hello")
    loaded = s.load(sid)
    assert loaded == msgs


def test_list_returns_saved():
    d = tempfile.mkdtemp()
    s = SessionStore(d)
    s.save([{"role": "user", "content": [{"type": "text", "text": "a"}]}], preview="a")
    items = s.list()
    assert len(items) == 1
    assert items[0]["preview"] == "a"
    assert items[0]["n_messages"] == 1


def test_load_missing_returns_none():
    d = tempfile.mkdtemp()
    s = SessionStore(d)
    assert s.load("nope") is None


def test_save_ids_unique_per_second():
    d = tempfile.mkdtemp()
    s = SessionStore(d)
    sid1 = s.save([{"role": "user", "content": [{"type": "text", "text": "a"}]}], preview="a")
    sid2 = s.save([{"role": "user", "content": [{"type": "text", "text": "b"}]}], preview="b")
    assert sid1 != sid2
    items = s.list()
    assert len(items) == 2


def test_resume_restores_messages_into_agent():
    from tests.helpers import build_agent

    d = tempfile.mkdtemp()
    s = SessionStore(d)
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "prior"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "reply"}]},
    ]
    sid = s.save(msgs, preview="prior")

    agent, _ = build_agent([[{"type": "text", "text": "ok"}]])
    agent.messages = s.load(sid)
    assert len(agent.messages) == 2
    assert agent.messages == msgs
