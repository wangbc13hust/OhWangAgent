import json
import os
import tempfile

from ohwang.services.mcp import MCPClient, MCPToolWrapper, load_mcp_tools
from ohwang.tools.registry import ToolRegistry


def test_mcp_tool_wrapper_name_prefix():
    class _FakeClient:
        name = "test_server"

    spec = {"name": "read_file", "description": "Read a file", "inputSchema": {"type": "object"}}
    wrapper = MCPToolWrapper(_FakeClient(), spec)
    assert wrapper.name == "mcp__test_server__read_file"
    assert wrapper.description == "Read a file"
    assert wrapper.default_permission == "ask"


def test_mcp_tool_wrapper_extract_text():
    result = {
        "content": [
            {"type": "text", "text": "hello world"},
            {"type": "image", "data": "..."},
        ]
    }
    assert MCPToolWrapper._extract_text(result) == "hello world"


def test_mcp_tool_wrapper_extract_text_fallback():
    result = {"some": "dict"}
    text = MCPToolWrapper._extract_text(result)
    assert "some" in text


def test_mcp_tool_wrapper_is_error():
    assert MCPToolWrapper._is_error({"isError": True}) is True
    assert MCPToolWrapper._is_error({"isError": False}) is False
    assert MCPToolWrapper._is_error({}) is False
    assert MCPToolWrapper._is_error("not a dict") is False


def test_load_mcp_tools_no_config():
    d = tempfile.mkdtemp()
    registry = ToolRegistry()
    added = load_mcp_tools(d, registry)
    assert added == []


def test_load_mcp_tools_with_invalid_config():
    d = tempfile.mkdtemp()
    mcp_dir = os.path.join(d, ".ohwang")
    os.makedirs(mcp_dir, exist_ok=True)
    with open(os.path.join(mcp_dir, "mcp.json"), "w") as f:
        f.write("invalid json")
    registry = ToolRegistry()
    added = load_mcp_tools(d, registry)
    assert added == []
