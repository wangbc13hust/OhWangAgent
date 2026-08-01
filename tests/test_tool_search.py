from ohwang.tools import default_tools
from ohwang.tools.bash import BashTool
from ohwang.tools.file_read import FileReadTool
from ohwang.tools.registry import ToolRegistry
from ohwang.tools.tool_search import ToolSearchTool


def test_tool_search_finds_by_name():
    registry = ToolRegistry()
    registry.register(BashTool())
    registry.register(FileReadTool())
    tool = ToolSearchTool(registry)
    result = tool.execute({"query": "read"})
    assert not result.is_error
    assert "file_read" in result.content


def test_tool_search_no_match():
    registry = ToolRegistry()
    registry.register(BashTool())
    tool = ToolSearchTool(registry)
    result = tool.execute({"query": "zzzqqq"})
    assert "No matches" in result.content


def test_tool_search_excludes_itself():
    registry = default_tools()
    tool = ToolSearchTool(registry)
    result = tool.execute({"query": "search tools"})
    assert "tool_search" not in result.content


def test_tool_search_respects_limit():
    registry = default_tools()
    tool = ToolSearchTool(registry)
    result = tool.execute({"query": "file", "limit": 2})
    matches = [l for l in result.content.splitlines() if l.startswith("  ")]
    assert len(matches) <= 2
