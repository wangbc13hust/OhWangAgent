"""Tests for the localhost HTTP daemon (ohwang serve): REST /run, SSE /stream,
session persistence, single-flight execution, and graceful shutdown.

All requests go over the loopback with a scripted provider — no network, no
real model (mirrors how the rest of the suite drives the agent).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from ohwang.services.server import run_server
from ohwang.services.session import SessionStore
from tests.helpers import ScriptedProvider, build_agent


class SlowScriptedProvider(ScriptedProvider):
    """ScriptedProvider that sleeps per chat() call (for single-flight)."""

    def __init__(self, responses, delay: float = 0.4):
        super().__init__(responses)
        self.delay = delay

    def chat(self, system, messages, tools, max_tokens):
        time.sleep(self.delay)
        yield from super().chat(system, messages, tools, max_tokens)


def _post(base: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _stream(base: str, body: dict) -> list[tuple[str, dict]]:
    """POST /stream and read the full SSE event list until the stream closes."""
    req = urllib.request.Request(
        base + "/stream",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    events: list[tuple[str, dict]] = []
    name: str | None = None
    for line in raw.splitlines():
        if line.startswith("event: "):
            name = line[len("event: "):].strip()
        elif line.startswith("data: ") and name is not None:
            events.append((name, json.loads(line[len("data: "):])))
    return events


class ServerFixture:
    """Starts run_server in a background thread; sets shutdown on exit."""

    def __init__(self, agent, session_store, memory_extractor=None, port=0):
        self.agent = agent
        self.session_store = session_store
        self.memory_extractor = memory_extractor
        self.port = port
        self.run_lock = threading.Lock()
        self.ready = threading.Event()
        self.shutdown = threading.Event()
        self.info: dict = {}
        self.result = None
        self._run_kwargs = dict(
            agent=agent,
            run_lock=self.run_lock,
            session_store=session_store,
            memory_extractor=memory_extractor,
            host="127.0.0.1",
            port=port,
            shutdown_event=self.shutdown,
            on_ready=lambda p: (self.info.update(port=p), self.ready.set()),
        )

        def _run():
            self.result = run_server(**self._run_kwargs)

        self.thread = threading.Thread(target=_run, daemon=True)

    def __enter__(self):
        self.thread.start()
        assert self.ready.wait(timeout=5), "server did not become ready"
        self.base = f"http://127.0.0.1:{self.info['port']}"
        return self

    def __exit__(self, *_exc):
        self.shutdown.set()
        self.thread.join(timeout=5)
        return False

    def post(self, path: str, body: dict) -> dict:
        return _post(self.base, path, body)

    def get(self, path: str) -> dict:
        return _get(self.base, path)


@pytest.fixture
def make_server(tmp_path, monkeypatch):
    """Factory that builds a server around a scripted agent per test.

    chdir into tmp_path first so any file tool side effects stay out of the
    repo (and the agent's workdir points somewhere disposable).
    """
    monkeypatch.chdir(tmp_path)
    servers: list[ServerFixture] = []

    def _make(responses, provider=None, memory_extractor=None):
        agent, _ = build_agent(responses)
        if provider is not None:
            agent.provider = provider
        store = SessionStore(str(tmp_path))
        fx = ServerFixture(agent, store, memory_extractor)
        servers.append(fx)
        return fx

    yield _make
    for fx in servers:
        fx.shutdown.set()
        fx.thread.join(timeout=5)


# ---- 1.3 health + localhost-only binding --------------------------------

def test_health_reports_ready(make_server):
    with make_server([[{"type": "text", "text": "hi"}]]) as s:
        health = s.get("/health")
        assert health["status"] == "ready"
        assert health["model"] == "scripted-model"


def test_unknown_route_returns_404(make_server):
    with make_server([[{"type": "text", "text": "hi"}]]) as s:
        req = urllib.request.Request(
            s.base + "/nope",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req, timeout=5)
        assert ei.value.code == 404


def test_binds_localhost_only(make_server):
    s = make_server([[{"type": "text", "text": "hi"}]])
    with s:
        assert s.get("/health")["status"] == "ready"
    # The bound address is only loopback — never 0.0.0.0 / the LAN interface.
    host, _port = s.result.server_address
    assert host == "127.0.0.1"


# ---- 2.2 single-flight ------------------------------------------------

def test_second_run_waits_for_first(make_server):
    responses = [
        [{"type": "text", "text": "first"}],
        [{"type": "text", "text": "second"}],
    ]
    slow = SlowScriptedProvider(responses, delay=0.3)
    with make_server(responses, provider=slow) as s:
        results: dict = {}
        t0 = time.monotonic()

        def call_one():
            results["r1"] = s.post("/run", {"message": "one"})
            results["t1"] = time.monotonic() - t0

        t1 = threading.Thread(target=call_one)
        t1.start()
        time.sleep(0.15)  # let the first run get in flight (holds the lock)
        t_req2 = time.monotonic()
        r2 = s.post("/run", {"message": "two"})
        req2_elapsed = time.monotonic() - t_req2
        t1.join(timeout=10)

        assert r2["final_text"] == "second"
        assert results["r1"]["final_text"] == "first"
        # The second request queued behind the first's ~0.3s run instead of
        # running concurrently.
        assert req2_elapsed >= 0.25


# ---- 2.3 session creation + resume ------------------------------------

def test_new_session_created_and_resumed(make_server):
    responses = [
        [{"type": "text", "text": "第一轮回复"}],
        [{"type": "text", "text": "第二轮回复"}],
    ]
    with make_server(responses) as s:
        r1 = s.post("/run", {"message": "第一轮问题"})
        assert "session_id" in r1
        assert r1["final_text"] == "第一轮回复"
        sid = r1["session_id"]

        loaded = s.session_store.load(sid)
        assert loaded is not None and len(loaded) >= 2

        r2 = s.post("/run", {"message": "第二轮问题", "session_id": sid})
        assert r2["final_text"] == "第二轮回复"
        assert r2["session_id"] == sid
        # The resumed run saw the prior history (provider's 2nd call input).
        calls = s.agent.provider.calls
        assert len(calls) == 2
        assert "第一轮问题" in json.dumps(calls[1]["messages"], ensure_ascii=False)


def test_unknown_session_returns_404(make_server):
    with make_server([[{"type": "text", "text": "hi"}]]) as s:
        with pytest.raises(urllib.error.HTTPError) as ei:
            s.post("/run", {"message": "hi", "session_id": "does-not-exist"})
        assert ei.value.code == 404


# ---- 3.2 / 3.3 SSE events ---------------------------------------------

def test_stream_events_ordered_before_done(make_server):
    responses = [
        [
            {"type": "text", "text": "开始处理"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "web_search",
                "input": {"query": "claude code"},
            },
        ],
        [{"type": "text", "text": "完成"}],
    ]
    with make_server(responses) as s:
        events = _stream(s.base, {"message": "查一下"})
    names = [name for name, _ in events]
    data = {name: d for name, d in events}
    # on_turn fires at the top of each iteration (before provider.chat), so
    # turn comes first; text/tool_call/tool_result must all precede done.
    done_idx = names.index("done")
    for ev in ("text", "tool_call", "tool_result"):
        assert ev in names
        assert names.index(ev) < done_idx
    assert names[-1] == "done"
    assert "session_id" in data["done"]
    tr = next(d for name, d in events if name == "tool_result")
    assert tr["tool"] == "web_search"
    assert tr["is_error"] is False


def test_stream_tool_result_carries_error_state(make_server):
    responses = [
        [{"type": "tool_use", "id": "t1", "name": "no_such_tool", "input": {}}],
        [{"type": "text", "text": "结束"}],
    ]
    with make_server(responses) as s:
        events = _stream(s.base, {"message": "触发错误"})
    tr = next(d for name, d in events if name == "tool_result")
    assert tr["is_error"] is True
    assert tr["tool"] == "no_such_tool"


def test_stream_emits_turn_progress(make_server):
    responses = [
        [
            {"type": "text", "text": "a"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "web_search",
                "input": {"query": "claude code"},
            },
        ],
        [{"type": "text", "text": "b"}],
    ]
    with make_server(responses) as s:
        events = _stream(s.base, {"message": "查一下"})
    turns = [d for name, d in events if name == "turn"]
    assert len(turns) == 2  # one per iteration
    assert turns[0]["iteration"] == 1
    assert turns[1]["iteration"] == 2


# ---- post-run mirror (memory extraction) --------------------------------

def test_post_run_calls_memory_extractor(make_server):
    calls = []

    class Extractor:
        def maybe_extract(self, provider, messages):
            calls.append(list(messages))
            return 0

    with make_server([[{"type": "text", "text": "hi"}]], memory_extractor=Extractor()) as s:
        s.post("/run", {"message": "记住这个事实"})
    assert len(calls) == 1
    assert any(
        "记住这个事实" in json.dumps(m, ensure_ascii=False) for m in calls[0]
    )


# ---- 4.1 graceful shutdown ---------------------------------------------

def test_shutdown_releases_port(make_server, tmp_path):
    store = SessionStore(str(tmp_path))
    agent, _ = build_agent([[{"type": "text", "text": "hi"}]])
    s1 = ServerFixture(agent, store, port=0)
    with s1:
        port = s1.info["port"]

    # Rebind the exact same port — proves the previous server released it.
    agent2, _ = build_agent([[{"type": "text", "text": "hi"}]])
    s2 = ServerFixture(agent2, store, port=port)
    with s2:
        assert s2.info["port"] == port
        assert s2.get("/health")["status"] == "ready"


def test_shutdown_lets_inflight_run_finish(make_server):
    responses = [[{"type": "text", "text": "done"}]]
    slow = SlowScriptedProvider(responses, delay=0.4)
    with make_server(responses, provider=slow) as s:
        out: dict = {}

        def run():
            out["r"] = s.post("/run", {"message": "x"})

        t = threading.Thread(target=run)
        t.start()
        time.sleep(0.1)  # the run is now in flight holding the lock
        s.shutdown.set()  # request shutdown while it is still running
        t.join(timeout=10)
        assert out["r"]["final_text"] == "done"
