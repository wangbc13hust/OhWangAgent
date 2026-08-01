import json
import os
import sys
import tempfile

import pytest

from ohwang.services.mcp import MCPClient, MCPToolWrapper, load_mcp_tools
from ohwang.tools.registry import ToolRegistry

FAKE_MCP_SERVER = r'''
import json
import sys

def respond(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if msg.get("method") == "initialize":
        respond({"jsonrpc": "2.0", "id": msg["id"], "result": {"capabilities": {}, "serverInfo": {"name": "fake", "version": "1"}}})
    elif msg.get("method") == "tools/list":
        respond({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "echo", "description": "Echo text", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}}]}})
    elif msg.get("method") == "tools/call":
        args = (msg.get("params") or {}).get("arguments", {})
        respond({"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": "echo:" + str(args.get("text", ""))}]}})
    elif msg.get("method") == "tools/call" and False:
        pass
'''

FAKE_MCP_SERVER_BAD_JSON = r'''
import sys
for line in sys.stdin:
    sys.stdout.write("{not json\n")
    sys.stdout.flush()
'''


def _spawn_client(code: str) -> MCPClient:
    client = MCPClient("test_server", sys.executable, ["-c", code])
    client.start()
    return client


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


def test_mcp_tool_wrapper_execute_ok():
    class _FakeClient:
        name = "test_server"

        def call_tool(self, name, args):
            return {"content": [{"type": "text", "text": "pong"}]}

    wrapper = MCPToolWrapper(_FakeClient(), {"name": "ping"})
    r = wrapper.execute({"ping": 1})
    assert not r.is_error
    assert r.content == "pong"


def test_mcp_tool_wrapper_execute_error():
    class _FakeClient:
        name = "test_server"

        def call_tool(self, name, args):
            raise RuntimeError("server exploded")

    wrapper = MCPToolWrapper(_FakeClient(), {"name": "ping"})
    r = wrapper.execute({})
    assert r.is_error
    assert "server exploded" in r.content


def test_mcp_client_handshake_list_and_call():
    client = _spawn_client(FAKE_MCP_SERVER)
    try:
        tools = client.list_tools()
        assert tools[0]["name"] == "echo"
        result = client.call_tool("echo", {"text": "hello"})
        assert result["content"][0]["text"] == "echo:hello"
    finally:
        client.stop()


def test_mcp_client_start_idempotent():
    client = _spawn_client(FAKE_MCP_SERVER)
    client.start()
    assert client._started
    client.stop()


class _FakeProc:
    def __init__(self, stdin_lines=None, stdout_lines=None):
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(stdout_lines or [])


class _FakeStdin:
    def __init__(self):
        self.written = ""

    def write(self, s):
        self.written += s

    def flush(self):
        pass


class _FakeStdout:
    def __init__(self, lines):
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


def test_mcp_client_send_timeout():
    client = MCPClient("test_server", sys.executable, ["-c", "import time; time.sleep(60)"])
    client._proc = _FakeProc()
    with pytest.raises(TimeoutError):
        client._send("tools/list", {}, timeout=0.1)


def test_mcp_client_read_loop_ignores_garbage():
    client = MCPClient("test_server", sys.executable, [])
    client._proc = _FakeProc(stdout_lines=["{not json\n", "    \n"])
    client._read_loop()
    assert client._responses == {}
    assert client._events == {}


def test_mcp_client_read_loop_captures_response():
    client = MCPClient("test_server", sys.executable, [])
    client._proc = _FakeProc(stdout_lines=[json.dumps({"jsonrpc": "2.0", "id": 7, "result": {}}) + "\n"])
    client._responses = {}
    client._events = {7: _FakeEvent()}
    client._read_loop()
    assert 7 in client._responses


class _FakeEvent:
    def __init__(self):
        self.set_called = False

    def set(self):
        self.set_called = True

    def wait(self, timeout=0):
        return True


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


def test_load_mcp_tools_success():
    d = tempfile.mkdtemp()
    mcp_dir = os.path.join(d, ".ohwang")
    os.makedirs(mcp_dir, exist_ok=True)
    config = {
        "mcpServers": {
            "fake": {"command": sys.executable, "args": ["-c", FAKE_MCP_SERVER]}
        }
    }
    with open(os.path.join(mcp_dir, "mcp.json"), "w", encoding="utf-8") as f:
        json.dump(config, f)
    registry = ToolRegistry()
    added = load_mcp_tools(d, registry)
    assert "mcp__fake__echo" in added
    assert "mcp__fake__echo" in registry


def test_load_mcp_tools_skips_failing_server():
    d = tempfile.mkdtemp()
    mcp_dir = os.path.join(d, ".ohwang")
    os.makedirs(mcp_dir, exist_ok=True)
    config = {
        "mcpServers": {
            "broken": {"command": sys.executable, "args": ["-c", "import sys; sys.exit(1)"]}
        }
    }
    with open(os.path.join(mcp_dir, "mcp.json"), "w", encoding="utf-8") as f:
        json.dump(config, f)
    registry = ToolRegistry()
    added = load_mcp_tools(d, registry)
    assert added == []
