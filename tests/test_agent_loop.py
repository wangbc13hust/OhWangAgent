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


if __name__ == "__main__":
    test_agent_loop()
