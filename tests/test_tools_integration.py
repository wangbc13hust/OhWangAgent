from ohwang.tools.lsp_diagnose import LSPDiagnoseTool
from ohwang.tools.memory import MemoryReadTool, MemoryWriteTool
from ohwang.tools.web_fetch import WebFetchTool
from ohwang.tools.web_search import WebSearchTool
from ohwang.tools.ask_user import AskUserQuestionTool
from ohwang.tools.agent_tool import AgentTool
from ohwang.tools.bash import BashTool
from ohwang.tools.file_read import FileReadTool
from ohwang.tools.file_write import FileWriteTool
from ohwang.tools.file_edit import FileEditTool
from ohwang.tools.glob import GlobTool
from ohwang.tools.grep import GrepTool
from ohwang.tools.todo import TodoWriteTool
from ohwang.tools.plan_mode import EnterPlanModeTool, ExitPlanModeTool
from ohwang.tools.registry import ToolRegistry
from ohwang.tools import default_tools
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
