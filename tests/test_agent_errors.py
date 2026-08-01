from ohwang.config import Config
from ohwang.modes import Mode
from ohwang.permissions import PermissionManager
from ohwang.providers.base import BaseProvider
from ohwang.tools.base import BaseTool, ToolResult
from tests.helpers import build_agent


class SequenceProvider(BaseProvider):
    """Yields one scripted event-list per chat() call, then stops."""

    name = "seq"

    def __init__(self, steps):
        super().__init__("k", "m")
        self.steps = steps
        self.i = 0

    def chat(self, system, messages, tools, max_tokens):
        if self.i < len(self.steps):
            yield from self.steps[self.i]
        self.i += 1


class ExplodingTool(BaseTool):
    name = "explode"
    description = ""
    input_schema = {"type": "object", "properties": {}}
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        raise RuntimeError("boom")


def _tool_results(agent):
    return [
        b
        for m in agent.messages
        for b in (m["content"] if isinstance(m.get("content"), list) else [])
        if b.get("type") == "tool_result"
    ]


def test_unknown_tool_reports_error():
    steps = [
        [{"type": "tool_use", "id": "x", "name": "no_such_tool", "input": {}}],
        [{"type": "text", "text": "done"}],
    ]
    agent, _ = build_agent([])
    agent.provider = SequenceProvider(steps)
    agent.run("go")
    results = _tool_results(agent)
    assert results and results[0]["is_error"]
    assert "Unknown tool" in results[0]["content"]


def test_permission_denied_blocks_tool():
    steps = [
        [{"type": "tool_use", "id": "x", "name": "bash", "input": {"command": "rm -rf"}}],
        [{"type": "text", "text": "denied"}],
    ]
    agent, _ = build_agent([], mode=Mode.DEFAULT)  # no ask callback -> ask tools denied
    agent.provider = SequenceProvider(steps)
    agent.run("go")
    results = _tool_results(agent)
    assert results and results[0]["is_error"]
    assert "Permission denied" in results[0]["content"]


def test_tool_exception_reported():
    steps = [
        [{"type": "tool_use", "id": "x", "name": "explode", "input": {}}],
        [{"type": "text", "text": "handled"}],
    ]
    agent, _ = build_agent([])
    agent.tools.register(ExplodingTool())
    agent.provider = SequenceProvider(steps)
    final = agent.run("go")
    results = _tool_results(agent)
    assert results and results[0]["is_error"]
    assert "Tool raised" in results[0]["content"]
    assert "RuntimeError" in results[0]["content"]
    assert "handled" in final


def test_single_turn_when_no_tool_use():
    steps = [[{"type": "text", "text": "hello"}]]
    agent, _ = build_agent([])
    agent.provider = SequenceProvider(steps)
    final = agent.run("hi")
    assert final == "hello"
    assert len(agent.messages) == 2  # user + assistant, no tool round


def test_max_iterations_caps_runaway_loop():
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "file_read",
                "input": {"file_path": "Z:/nope/nope.txt"},
            }
        ]
    ]
    agent, _ = build_agent([])
    agent.provider = SequenceProvider(steps * 1000)
    agent.run("loop", max_iterations=10)
    assert agent.iterations == 10


def test_reset_clears_messages():
    steps = [[{"type": "text", "text": "hi"}]]
    agent, _ = build_agent([])
    agent.provider = SequenceProvider(steps)
    agent.run("hello")
    assert len(agent.messages) >= 2
    agent.reset()
    assert agent.messages == []
    assert agent.iterations == 0
