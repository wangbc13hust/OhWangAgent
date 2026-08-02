"""Dangerous command pattern guard tests."""

from __future__ import annotations

from ohwang.agent import Agent
from ohwang.config import Config
from ohwang.modes import Mode
from ohwang.permissions import PermissionManager
from ohwang.services.guards import dangerous_command_hook
from ohwang.services.hooks import HookManager
from ohwang.tools.base import BaseTool, ToolResult
from ohwang.tools.registry import ToolRegistry


class Bash(BaseTool):
    name = "bash"
    description = "run a shell command"
    input_schema = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }

    def execute(self, input):
        return ToolResult(content="ok")


def test_handler_blocks_destructive_rm_root():
    r = dangerous_command_hook("bash", {"command": "rm -rf /"})
    assert r and r["block"] is True


def test_handler_blocks_home_and_git_force():
    for cmd in [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf $HOME",
        "rm -rf /home",
        "git push --force origin main",
        "git push -f",
        "git reset --hard",
    ]:
        r = dangerous_command_hook("bash", {"command": cmd})
        assert r and r["block"] is True, cmd


def test_handler_allows_safe_commands():
    for cmd in [
        "ls -la",
        "git status",
        "git push origin main",
        "git clean -n",
        "rm -rf ./build/tmp",
        "rm -rf /tmp/build",
        "rm -rf ~/projects/x",
        "echo reboot",
    ]:
        assert dangerous_command_hook("bash", {"command": cmd}) is None, cmd


def test_handler_ignores_non_shell_tools():
    assert dangerous_command_hook("file_read", {"file_path": "/"}) is None
    assert dangerous_command_hook("bash", {"command": 123}) is None


def _blocked_agent():
    hooks = HookManager()
    hooks.register("pre_tool_use", dangerous_command_hook)
    return Agent(
        provider=None,
        tools=ToolRegistry().register(Bash()),
        permissions=PermissionManager(mode=Mode.AUTO),
        config=Config(workdir=".").resolve(),
        system="sys",
        hooks=hooks,
    )


def test_hook_blocks_tool_through_agent():
    agent = _blocked_agent()
    block = agent._run_tool(
        {"name": "bash", "id": "1", "input": {"command": "rm -rf /"}}
    )
    assert block["is_error"] is True
    assert "Blocked by hook:" in block["content"]
    assert "Dangerous command pattern" in block["content"]


def test_hook_allows_safe_tool_through_agent():
    agent = _blocked_agent()
    ok = agent._run_tool({"name": "bash", "id": "2", "input": {"command": "ls -la"}})
    assert ok["is_error"] is False
    assert ok["content"] == "ok"
