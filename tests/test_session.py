import json
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


def test_save_summary_and_load_full():
    d = tempfile.mkdtemp()
    s = SessionStore(d)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    sid = s.save(msgs, preview="hello", summary="brief")
    data = s.load_full(sid)
    assert data["summary"] == "brief"
    assert data["messages"] == msgs
    assert s.load(sid) == msgs  # load() still returns messages only


def test_load_full_old_session_no_summary():
    d = tempfile.mkdtemp()
    s = SessionStore(d)
    sid = s.save([{"role": "user", "content": [{"type": "text", "text": "x"}]}])
    # strip the summary field to simulate a pre-summary session file
    path = s.dir / f"{sid}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("summary", None)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert s.load_full(sid).get("summary", "") == ""


def test_summarizer_returns_text():
    from ohwang.services.summarizer import SessionSummarizer
    from tests.helpers import ScriptedProvider

    provider = ScriptedProvider([[{"type": "text", "text": "- goal: build things"}]])
    out = SessionSummarizer().summarize(
        provider, [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    )
    assert out == "- goal: build things"


def test_summarizer_degrades_on_error():
    from ohwang.services.summarizer import SessionSummarizer

    class Boom:
        def chat(self, *a, **k):
            raise RuntimeError("down")
            yield  # noqa

    out = SessionSummarizer().summarize(
        Boom(), [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    )
    assert out == ""


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
