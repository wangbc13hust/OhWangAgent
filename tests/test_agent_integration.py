from ohwang.providers.base import BaseProvider
from ohwang.services.hooks import HookManager
from ohwang.services.policy import PolicyLimits
from ohwang.services.summary import UsageTracker
from tests.helpers import build_agent


class Seq(BaseProvider):
    name = "seq"

    def __init__(self, steps):
        super().__init__("k", "m")
        self.steps = steps
        self.i = 0

    def chat(self, system, messages, tools, max_tokens):
        if self.i < len(self.steps):
            yield from self.steps[self.i]
        self.i += 1


def _results(agent):
    return [
        b
        for m in agent.messages
        for b in (m["content"] if isinstance(m.get("content"), list) else [])
        if b.get("type") == "tool_result"
    ]


def test_agent_hook_blocks_tool():
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "file_write",
                "input": {"file_path": "x", "content": "y"},
            }
        ],
        [{"type": "text", "text": "blocked"}],
    ]
    agent, _ = build_agent([])
    hooks = HookManager()
    hooks.register("pre_tool_use", lambda name, inp: False if name == "file_write" else None)
    agent.hooks = hooks
    agent.provider = Seq(steps)
    agent.run("go")
    results = _results(agent)
    assert results and results[0]["is_error"]
    assert "Blocked by hook" in results[0]["content"]


def test_agent_policy_caps_tool(tmp_path):
    real = tmp_path / "real.txt"
    real.write_text("hi", encoding="utf-8")
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "file_read",
                "input": {"file_path": str(real)},
            }
        ],
        [
            {
                "type": "tool_use",
                "id": "y",
                "name": "file_read",
                "input": {"file_path": str(real)},
            }
        ],
        [{"type": "text", "text": "done"}],
    ]
    agent, _ = build_agent([])
    agent.policy = PolicyLimits(per_tool={"file_read": 1})
    agent.provider = Seq(steps)
    agent.run("go")
    results = _results(agent)
    assert len(results) == 2
    assert not results[0]["is_error"]
    assert results[1]["is_error"]
    assert "Policy limit" in results[1]["content"]


def test_agent_usage_records_calls():
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "file_read",
                "input": {"file_path": "Z:/nope.txt"},
            }
        ],
        [{"type": "text", "text": "done"}],
    ]
    agent, _ = build_agent([])
    usage = UsageTracker()
    agent.usage = usage
    agent.provider = Seq(steps)
    agent.run("go")
    assert usage.total == 1
    assert usage.calls_for("file_read") == 1
    assert usage.errors_for("file_read") == 1


def test_default_tools_registers_new_extensions():
    from ohwang.tools import default_tools
    from ohwang.modes import Mode
    from ohwang.permissions import PermissionManager
    from tests.helpers import MockSearchProvider

    registry = default_tools(
        todo_store=None,
        permissions=PermissionManager(mode=Mode.AUTO),
        search_provider=MockSearchProvider(),
    )
    names = registry.names()
    assert "sleep" in names
    assert "config" in names
    assert "synthetic_output" in names
    assert "brief" in names
    assert "snip" in names


def test_agent_synthetic_output_shown_and_minimal_context():
    shown = []
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "synthetic_output",
                "input": {"text": "long report body the model must not re-read"},
            }
        ],
        [{"type": "text", "text": "done"}],
    ]
    agent, _ = build_agent([])
    from ohwang.tools.synthetic_output import SyntheticOutputTool

    agent.tools.register(SyntheticOutputTool(display=shown.append))
    agent.provider = Seq(steps)
    agent.run("go")
    assert shown == ["long report body the model must not re-read"]
    results = _results(agent)
    assert results[0]["content"] == "(shown to user)"
    assert "long report body" not in results[0]["content"]


def test_agent_brief_returns_summary_in_context():
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "brief",
                "input": {"focus": "progress"},
            }
        ],
        [{"type": "text", "text": "ok"}],
    ]
    agent, _ = build_agent([])
    usage = UsageTracker()
    usage.record("file_read", False)
    from ohwang.tools.brief import BriefTool

    agent.tools.register(BriefTool(usage, None, lambda: agent.iterations))
    agent.provider = Seq(steps)
    agent.run("go")
    results = _results(agent)
    assert results[0]["content"].startswith("Session brief")
    assert "Tool calls: 1" in results[0]["content"]
