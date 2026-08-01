from ohwang.modes import Mode
from ohwang.permissions import PermissionManager
from ohwang.tools import default_tools


def _tools():
    return default_tools()


def test_plan_mode_blocks_write_tools():
    perms = PermissionManager(mode=Mode.PLAN)
    tools = _tools()
    assert perms.can_run(tools.get("bash"), {"command": "echo hi"}) is False
    assert perms.can_run(tools.get("file_write"), {"file_path": "x", "content": "y"}) is False
    assert perms.can_run(tools.get("file_edit"), {"file_path": "x", "old_string": "a", "new_string": "b"}) is False


def test_plan_mode_allows_read_tools():
    perms = PermissionManager(mode=Mode.PLAN)
    tools = _tools()
    assert perms.can_run(tools.get("file_read"), {"file_path": "x"}) is True
    assert perms.can_run(tools.get("grep"), {"pattern": "x"}) is True
    assert perms.can_run(tools.get("glob"), {"pattern": "*.py"}) is True


def test_default_mode_read_allows_write_denied_without_callback():
    perms = PermissionManager(mode=Mode.DEFAULT)
    tools = _tools()
    assert perms.can_run(tools.get("file_read"), {"file_path": "x"}) is True
    assert perms.can_run(tools.get("file_write"), {"file_path": "x", "content": "y"}) is False


def test_auto_mode_allows_all():
    perms = PermissionManager(mode=Mode.AUTO)
    tools = _tools()
    assert perms.can_run(tools.get("bash"), {"command": "x"}) is True
    assert perms.can_run(tools.get("file_write"), {"file_path": "x", "content": "y"}) is True


def test_plan_mode_tools_toggle_state():
    from ohwang.tools.plan_mode import EnterPlanModeTool, ExitPlanModeTool

    perms = PermissionManager(mode=Mode.DEFAULT)
    EnterPlanModeTool(perms).execute({})
    assert perms.mode is Mode.PLAN
    ExitPlanModeTool(perms).execute({})
    assert perms.mode is Mode.DEFAULT


def test_plan_mode_actually_blocks_in_agent_loop():
    from tests.helpers import build_agent

    agent, provider = build_agent(
        [
            [
                {"type": "text", "text": "trying to write"},
                {"type": "tool_use", "id": "t1", "name": "file_write", "input": {"file_path": "blocked.txt", "content": "x"}},
            ],
            [{"type": "text", "text": "ok"}],
        ],
        mode=Mode.PLAN,
    )
    agent.run("write a file")
    tool_results = [
        b for m in agent.messages for b in m.get("content", [])
        if isinstance(m.get("content"), list) and b.get("type") == "tool_result"
    ]
    assert tool_results
    assert tool_results[0]["is_error"] is True
    assert "denied" in tool_results[0]["content"].lower()
