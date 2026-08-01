from ohwang.services.scheduler import Scheduler
from ohwang.tools.schedule import CronCreateTool, CronDeleteTool, CronListTool
from ohwang.tools import default_tools
from ohwang.tools.registry import ToolRegistry
from ohwang.tools.bash import BashTool
from ohwang.permissions import PermissionManager
from ohwang.modes import Mode
from ohwang.tools.todo import TodoStore
from tests.helpers import MockSearchProvider


def test_default_tools_includes_core():
    registry = default_tools(
        todo_store=TodoStore(),
        permissions=PermissionManager(mode=Mode.AUTO),
        search_provider=MockSearchProvider(),
    )
    names = registry.names()
    assert "bash" in names
    assert "file_read" in names
    assert "file_write" in names
    assert "file_edit" in names
    assert "grep" in names
    assert "glob" in names
    assert "web_fetch" in names
    assert "web_search" in names
    assert "todo_write" in names
    assert "enter_plan_mode" in names
    assert "exit_plan_mode" in names


def test_default_tools_without_todo():
    registry = default_tools(search_provider=MockSearchProvider())
    names = registry.names()
    assert "todo_write" not in names
    assert "bash" in names


def test_default_tools_without_permissions():
    registry = default_tools(search_provider=MockSearchProvider())
    names = registry.names()
    assert "enter_plan_mode" not in names
    assert "exit_plan_mode" not in names


def test_default_tools_with_ask_callback():
    registry = default_tools(
        search_provider=MockSearchProvider(),
        ask_callback=lambda q, o: "yes",
    )
    names = registry.names()
    assert "ask_user_question" in names


def test_default_tools_with_agent_factory():
    registry = default_tools(
        search_provider=MockSearchProvider(),
        agent_factory=lambda: None,
    )
    names = registry.names()
    assert "agent" in names


def test_default_tools_includes_new_extensions():
    registry = default_tools(search_provider=MockSearchProvider())
    names = registry.names()
    assert "powershell" in names
    assert "tool_search" in names
    assert "enter_worktree" in names
    assert "exit_worktree" in names
    assert "browser_action" not in names  # playwright not installed


def test_default_tools_with_scheduler_registers_cron():
    registry = default_tools(
        search_provider=MockSearchProvider(),
        scheduler=Scheduler(),
    )
    names = registry.names()
    assert "cron_create" in names
    assert "cron_delete" in names
    assert "cron_list" in names


def test_cron_tools_roundtrip():
    scheduler = Scheduler()
    create = CronCreateTool(scheduler)
    delete = CronDeleteTool(scheduler)
    listing = CronListTool(scheduler)

    r = create.execute({"id": "t", "expression": "*/30 * * * *", "prompt": "run tests"})
    assert not r.is_error
    r2 = listing.execute({})
    assert "t" in r2.content
    r3 = delete.execute({"id": "t"})
    assert not r3.is_error
    r4 = delete.execute({"id": "t"})
    assert r4.is_error


def test_all_tools_have_valid_specs():
    registry = default_tools(
        todo_store=TodoStore(),
        permissions=PermissionManager(mode=Mode.AUTO),
        search_provider=MockSearchProvider(),
    )
    specs = registry.specs()
    assert len(specs) >= 10
    for s in specs:
        assert "name" in s
        assert "description" in s
        assert "input_schema" in s
        assert s["name"] != ""


def test_tool_registry_duplicate_overwrite():
    registry = ToolRegistry()
    registry.register(BashTool())
    registry.register(BashTool())
    assert len(registry) == 1


def test_tool_registry_get_unknown():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_all_tool_schemas_are_valid_json_schema():
    registry = default_tools(
        todo_store=TodoStore(),
        permissions=PermissionManager(mode=Mode.AUTO),
        search_provider=MockSearchProvider(),
    )
    for tool in registry:
        schema = tool.input_schema
        assert isinstance(schema, dict)
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
