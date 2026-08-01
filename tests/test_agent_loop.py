from __future__ import annotations

import os
import tempfile

from ohwang.agent import Agent
from ohwang.config import Config
from ohwang.permissions import PermissionManager
from ohwang.prompts import build_system_prompt
from ohwang.providers.base import BaseProvider
from ohwang.tools import default_tools


class MockProvider(BaseProvider):
    name = "mock"

    def __init__(self) -> None:
        super().__init__("fake-key", "mock-model")
        self.calls = 0
        self.seen_messages: list = []

    def chat(self, system, messages, tools, max_tokens):
        self.calls += 1
        self.seen_messages = list(messages)
        if self.calls == 1:
            yield {"type": "text", "text": "I'll read the file first."}
            yield {
                "type": "tool_use",
                "id": "t1",
                "name": "file_read",
                "input": {"file_path": "_mock.txt"},
            }
        else:
            yield {"type": "text", "text": "Done. The file says: mock content."}


def test_agent_loop():
    workdir = tempfile.mkdtemp()
    os.chdir(workdir)
    with open("_mock.txt", "w", encoding="utf-8") as f:
        f.write("mock content line1\nmock content line2\n")

    config = Config(workdir=workdir, auto_approve=True).resolve()
    provider = MockProvider()
    tools = default_tools()
    permissions = PermissionManager(auto_approve=True)
    agent = Agent(provider, tools, permissions, config, build_system_prompt(workdir))

    events: list = []
    final = agent.run(
        "read _mock.txt",
        on_text=lambda t: events.append(("text", t)),
        on_tool_call=lambda tu: events.append(("call", tu["name"])),
        on_tool_result=lambda n, e: events.append(("result", n, e)),
    )

    assert provider.calls == 2, f"expected 2 iterations, got {provider.calls}"
    assert "Done" in final

    tool_results = [
        b
        for m in agent.messages
        for b in (m["content"] if isinstance(m.get("content"), list) else [])
        if b.get("type") == "tool_result"
    ]
    assert tool_results, "no tool_result block found in messages"
    tr = tool_results[0]
    assert "mock content line1" in tr["content"]
    assert not tr["is_error"]
    assert ("call", "file_read") in events
    assert ("result", "file_read", False) in events
    print("PASS: agent loop ran 2 iterations, executed file_read, fed result back.")


def test_effective_system_injects_memory_context():
    from ohwang.services.memory import MemoryStore

    workdir = tempfile.mkdtemp()
    store = MemoryStore(workdir)
    store.add_fact("test_cmd", "pytest -q", tags=["test"])

    config = Config(workdir=workdir, auto_approve=True).resolve()
    provider = MockProvider()
    tools = default_tools(memory_store=store)
    permissions = PermissionManager(auto_approve=True)
    agent = Agent(
        provider, tools, permissions, config, build_system_prompt(workdir),
        memory_store=store,
    )

    system = agent._effective_system()
    assert "pytest -q" in system
    assert "test_cmd" in system
    assert "Project Memory" in system


def test_effective_system_injects_session_summary():
    workdir = tempfile.mkdtemp()
    config = Config(workdir=workdir, auto_approve=True).resolve()
    provider = MockProvider()
    agent = Agent(
        provider, default_tools(), PermissionManager(auto_approve=True),
        config, build_system_prompt(workdir),
        session_summary="- resumed task: write report",
    )
    system = agent._effective_system()
    assert "Session Context" in system
    assert "resumed task" in system


def test_effective_system_without_memory():
    workdir = tempfile.mkdtemp()
    config = Config(workdir=workdir, auto_approve=True).resolve()
    provider = MockProvider()
    agent = Agent(
        provider, default_tools(), PermissionManager(auto_approve=True),
        config, build_system_prompt(workdir),
    )
    assert agent._effective_system() == build_system_prompt(workdir)


class ReactiveProvider(BaseProvider):
    """Call 1 raises prompt-too-long; call 2 is the compact summary call;
    call 3 is the retried main chat."""

    name = "reactive"

    def __init__(self) -> None:
        super().__init__("fake-key", "reactive-model")
        self.calls = 0

    def chat(self, system, messages, tools, max_tokens):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError(
                "API request failed: prompt is too long (max 1000 tokens)"
            )
            yield  # noqa
        if self.calls == 2:
            yield {"type": "text", "text": "SUMMARY: earlier work"}
        else:
            yield {"type": "text", "text": "Recovered after compaction."}


def test_reactive_compact_retries_on_ptl():
    from ohwang.services.compact import Compactor

    workdir = tempfile.mkdtemp()
    config = Config(workdir=workdir, auto_approve=True).resolve()
    provider = ReactiveProvider()
    compactor = Compactor(threshold_tokens=1_000_000, keep_recent=2, max_tokens=64)
    agent = Agent(
        provider, default_tools(), PermissionManager(auto_approve=True),
        config, build_system_prompt(workdir), compactor=compactor,
    )
    # pre-seed enough history that compact() actually summarizes old messages
    agent.messages = [
        {"role": "user", "content": [{"type": "text", "text": "task start"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "doing work"}]},
        {"role": "user", "content": [{"type": "text", "text": "context"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "result"}]},
    ]

    final = agent.run("continue now")
    assert provider.calls == 3
    assert "Recovered after compaction" in final
    texts = " ".join(
        b.get("text", "")
        for m in agent.messages
        for b in (m["content"] if isinstance(m.get("content"), list) else [])
        if b.get("type") == "text"
    )
    assert "SUMMARY" in texts


def test_reactive_raises_on_non_ptl():
    import pytest
    from ohwang.services.compact import Compactor

    class BoomProvider(BaseProvider):
        name = "boom"

        def __init__(self) -> None:
            super().__init__("k", "m")
            self.calls = 0

        def chat(self, system, messages, tools, max_tokens):
            self.calls += 1
            raise RuntimeError("rate limit exceeded")
            yield  # noqa

    workdir = tempfile.mkdtemp()
    config = Config(workdir=workdir, auto_approve=True).resolve()
    provider = BoomProvider()
    compactor = Compactor(threshold_tokens=1_000_000, keep_recent=2, max_tokens=64)
    agent = Agent(
        provider, default_tools(), PermissionManager(auto_approve=True),
        config, build_system_prompt(workdir), compactor=compactor,
    )
    with pytest.raises(RuntimeError, match="rate limit"):
        agent.run("hi")
    assert provider.calls == 1  # non-PTL errors are not retried


if __name__ == "__main__":
    test_agent_loop()
    test_effective_system_injects_memory_context()
    test_effective_system_without_memory()
