from ohwang.agent import Agent
from ohwang.config import Config
from ohwang.modes import Mode
from ohwang.permissions import PermissionManager
from ohwang.prompts import SYSTEM_PROMPT
from ohwang.providers.base import BaseProvider
from ohwang.tools.agent_tool import AgentTool
from ohwang.tools import default_tools
from ohwang.tools.todo import TodoStore


class _SubProvider(BaseProvider):
    name = "sub_mock"

    def __init__(self):
        super().__init__("fake-key", "sub-model")
        self.called = False

    def chat(self, system, messages, tools, max_tokens):
        self.called = True
        yield {"type": "text", "text": "sub-agent result"}


def test_agent_tool_spawns_sub_agent():
    def factory():
        config = Config(workdir=".", auto_approve=True).resolve()
        perms = PermissionManager(mode=Mode.AUTO)
        provider = _SubProvider()
        tools = default_tools(
            todo_store=TodoStore(),
            permissions=perms,
            search_provider=None,
        )
        return Agent(provider, tools, perms, config, SYSTEM_PROMPT)

    tool = AgentTool(factory)
    r = tool.execute({
        "description": "test task",
        "prompt": "do something",
    })
    assert r.is_error is False
    assert "sub-agent result" in r.content


def test_agent_tool_handles_sub_agent_failure():
    def factory():
        class _FailingAgent:
            def run(self, prompt, **kwargs):
                raise RuntimeError("sub boom")
        return _FailingAgent()

    tool = AgentTool(factory)
    r = tool.execute({
        "description": "fail task",
        "prompt": "fail",
    })
    assert r.is_error is True
    assert "failed" in r.content.lower()


def test_agent_tool_schema():
    tool = AgentTool(lambda: None)
    assert tool.name == "agent"
    assert tool.default_permission == "allow"
    assert "prompt" in tool.input_schema["properties"]
