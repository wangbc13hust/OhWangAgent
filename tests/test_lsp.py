from ohwang.services.lsp import (
    LSPClient,
    load_lsp_tools,
    _path_to_uri,
    _guess_language,
    _severity_name,
    _read_file,
    _rpc_call,
    _rpc_notify,
)
from ohwang.tools.lsp_diagnose import LSPDiagnoseTool
from ohwang.tools.registry import ToolRegistry
import tempfile
import os
import json
import sys


def test_path_to_uri():
    uri = _path_to_uri("C:/Users/test/project/file.py")
    assert uri.startswith("file:///")
    assert "file.py" in uri


def test_guess_language():
    assert _guess_language("app.py") == "python"
    assert _guess_language("app.ts") == "typescript"
    assert _guess_language("app.tsx") == "typescriptreact"
    assert _guess_language("app.js") == "javascript"
    assert _guess_language("app.jsx") == "javascriptreact"
    assert _guess_language("app.go") == "go"
    assert _guess_language("app.rs") == "rust"
    assert _guess_language("app.java") == "java"
    assert _guess_language("app.c") == "c"
    assert _guess_language("app.cpp") == "cpp"
    assert _guess_language("app.unknown") == "plaintext"


def test_severity_name():
    assert _severity_name(1) == "error"
    assert _severity_name(2) == "warning"
    assert _severity_name(3) == "info"
    assert _severity_name(4) == "hint"
    assert _severity_name(99) == "error"


def test_read_file():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "test.txt")
    with open(path, "w") as f:
        f.write("hello")
    assert _read_file(path) == "hello"
    assert _read_file(os.path.join(d, "nope.txt")) is None


def test_lsp_diagnose_tool_no_client():
    tool = LSPDiagnoseTool(client=None)
    r = tool.execute({"file_path": "some.py"})
    assert r.is_error is True
    assert "not configured" in r.content.lower()


def test_lsp_diagnose_tool_file_not_found():
    tool = LSPDiagnoseTool(client="fake")
    r = tool.execute({"file_path": "nonexistent_file_12345.py"})
    assert r.is_error is True
    assert "not found" in r.content.lower()


def test_lsp_diagnose_tool_schema():
    tool = LSPDiagnoseTool()
    assert tool.name == "lsp_diagnose"
    assert tool.default_permission == "allow"
    assert "file_path" in tool.input_schema["properties"]


def test_lsp_diagnose_tool_with_diagnostics(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("x = 1\n", encoding="utf-8")

    class _Client:
        def diagnose(self, path):
            return [{"severity": "error", "message": "bad type", "line": 1}]

    tool = LSPDiagnoseTool(client=_Client())
    r = tool.execute({"file_path": str(p)})
    assert not r.is_error
    assert "ERROR line 1: bad type" in r.content


def test_lsp_diagnose_tool_no_issues(tmp_path):
    p = tmp_path / "b.py"
    p.write_text("x = 1\n", encoding="utf-8")

    class _Client:
        def diagnose(self, path):
            return []

    tool = LSPDiagnoseTool(client=_Client())
    r = tool.execute({"file_path": str(p)})
    assert not r.is_error
    assert "No issues found" in r.content


def test_lsp_diagnose_tool_wraps_client_error(tmp_path):
    p = tmp_path / "c.py"
    p.write_text("x = 1\n", encoding="utf-8")

    class _Client:
        def diagnose(self, path):
            raise RuntimeError("lsp crashed")

    tool = LSPDiagnoseTool(client=_Client())
    r = tool.execute({"file_path": str(p)})
    assert r.is_error
    assert "lsp crashed" in r.content


def test_load_lsp_tools_no_config():
    d = tempfile.mkdtemp()
    registry = ToolRegistry()
    added = load_lsp_tools(d, registry)
    assert added == []


def test_load_lsp_tools_invalid_config():
    d = tempfile.mkdtemp()
    lsp_dir = os.path.join(d, ".ohwang")
    os.makedirs(lsp_dir, exist_ok=True)
    with open(os.path.join(lsp_dir, "lsp.json"), "w") as f:
        f.write("invalid json")
    registry = ToolRegistry()
    added = load_lsp_tools(d, registry)
    assert added == []


def test_load_lsp_tools_command_not_found():
    d = tempfile.mkdtemp()
    lsp_dir = os.path.join(d, ".ohwang")
    os.makedirs(lsp_dir, exist_ok=True)
    with open(os.path.join(lsp_dir, "lsp.json"), "w") as f:
        json.dump({"command": "definitely_missing_lsp_server_xyz"}, f)
    registry = ToolRegistry()
    added = load_lsp_tools(d, registry)
    assert added == []


def test_load_lsp_tools_empty_servers_format():
    d = tempfile.mkdtemp()
    lsp_dir = os.path.join(d, ".ohwang")
    os.makedirs(lsp_dir, exist_ok=True)
    with open(os.path.join(lsp_dir, "lsp.json"), "w") as f:
        json.dump({"servers": {"pyright": {"command": "definitely_missing_lsp_server_xyz"}}}, f)
    registry = ToolRegistry()
    added = load_lsp_tools(d, registry)
    assert added == []


def test_load_lsp_tools_missing_command_field():
    d = tempfile.mkdtemp()
    lsp_dir = os.path.join(d, ".ohwang")
    os.makedirs(lsp_dir, exist_ok=True)
    with open(os.path.join(lsp_dir, "lsp.json"), "w") as f:
        json.dump({"servers": {"pyright": {"args": ["--stdio"]}}}, f)
    registry = ToolRegistry()
    added = load_lsp_tools(d, registry)
    assert added == []


# ---------- RPC framing helpers ----------

class _FakeIn:
    def __init__(self):
        self.data = ""

    def write(self, s):
        self.data += s

    def flush(self):
        pass


class _FakeOut:
    def __init__(self, data=""):
        self.data = data
        self.pos = 0

    def readline(self):
        if self.pos >= len(self.data):
            return ""
        end = self.data.find("\n", self.pos)
        if end == -1:
            end = len(self.data)
        line = self.data[self.pos : end + 1]
        self.pos = end + 1
        return line

    def read(self, n):
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk


class _FakeProc:
    def __init__(self, out_data=""):
        self.stdin = _FakeIn()
        self.stdout = _FakeOut(out_data)


def test_rpc_call_roundtrip():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    header = f"Content-Length: {len(body.encode())}\r\n\r\n"
    proc = _FakeProc(out_data=header + body)
    result = _rpc_call(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert result == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}


def test_rpc_call_write_failure_returns_none():
    proc = _FakeProc()

    class _Boom:
        def write(self, s):
            raise OSError("closed")

    proc.stdin = _Boom()
    assert _rpc_call(proc, {"jsonrpc": "2.0", "id": 1, "method": "x"}) is None


def test_rpc_call_empty_response_returns_none():
    proc = _FakeProc(out_data="")
    assert _rpc_call(proc, {"jsonrpc": "2.0", "id": 1, "method": "x"}) is None


def test_rpc_call_bad_header_returns_none():
    proc = _FakeProc(out_data="not-content-length\r\n\r\n")
    assert _rpc_call(proc, {"jsonrpc": "2.0", "id": 1, "method": "x"}) is None


def test_rpc_notify_writes_header():
    proc = _FakeProc()
    _rpc_notify(proc, {"jsonrpc": "2.0", "method": "exit"})
    assert "Content-Length:" in proc.stdin.data
    assert "exit" in proc.stdin.data


def test_rpc_notify_write_failure_safe():
    proc = _FakeProc()

    class _Boom:
        def write(self, s):
            raise OSError("closed")

    proc.stdin = _Boom()
    _rpc_notify(proc, {"jsonrpc": "2.0", "method": "exit"})  # must not raise


# ---------- LSPClient lifecycle ----------

def test_lsp_client_diagnose_before_init_returns_empty():
    client = LSPClient("cmd", [])
    assert client.diagnose("whatever.py") == []


def test_lsp_client_stop_without_start():
    client = LSPClient("cmd", [])
    client.stop()  # must not raise


def test_lsp_client_send_without_proc():
    client = LSPClient("cmd", [])
    assert client._send("shutdown", None) is None


FAKE_LSP = r'''
import json
import sys

def read_msg():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        key, _, value = line.decode().partition(":")
        headers[key.strip().lower()] = value.strip()
    n = int(headers.get("content-length", "0"))
    if n == 0:
        return None
    return json.loads(sys.stdin.buffer.read(n))

def send(obj):
    body = json.dumps(obj).encode()
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    sys.stdout.buffer.flush()

while True:
    msg = read_msg()
    if msg is None:
        break
    method = msg.get("method")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"capabilities": {}}})
    elif method == "textDocument/diagnostic":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"items": [
            {"severity": 1, "message": "undefined variable", "range": {"start": {"line": 2}}}
        ]}})
    elif method == "shutdown":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
'''


def test_lsp_client_full_flow(monkeypatch):
    d = tempfile.mkdtemp()
    src = os.path.join(d, "bug.py")
    with open(src, "w", encoding="utf-8") as f:
        f.write("x = 1\ny = 2\nfoo()\n")
    client = LSPClient(sys.executable, ["-c", FAKE_LSP], workdir=d)
    responses = [
        {"capabilities": {}},
        {
            "items": [
                {
                    "severity": 1,
                    "message": "undefined variable",
                    "range": {"start": {"line": 2}},
                }
            ]
        },
    ]

    def fake_send(method, params, timeout=30):
        if method == "initialize":
            return responses[0]
        if method == "textDocument/diagnostic":
            return responses[1]
        return None

    client._send = fake_send
    client._notify = lambda method, params=None: None
    client._initialized = True
    diags = client.diagnose(src)
    assert diags[0]["severity"] == "error"
    assert diags[0]["message"] == "undefined variable"
    assert diags[0]["line"] == 3


def test_lsp_client_initialize_sets_flag(monkeypatch):
    client = LSPClient("cmd", [])
    called = {"notify": False}
    client._send = lambda method, params, timeout=30: {"capabilities": {}}
    client._notify = lambda method, params=None: called.__setitem__("notify", True)
    client._initialize()
    assert client._initialized
    assert called["notify"]


def test_lsp_client_diagnose_no_result_returns_empty(monkeypatch):
    d = tempfile.mkdtemp()
    src = os.path.join(d, "a.py")
    with open(src, "w", encoding="utf-8") as f:
        f.write("x = 1\n")
    client = LSPClient("cmd", [])
    client._send = lambda method, params, timeout=30: None
    client._notify = lambda method, params=None: None
    client._initialized = True
    assert client.diagnose(src) == []


def test_lsp_client_diagnose_missing_file(monkeypatch):
    client = LSPClient("cmd", [])
    client._send = lambda method, params, timeout=30: None
    client._notify = lambda method, params=None: None
    client._initialized = True
    assert client.diagnose(os.path.join(tempfile.mkdtemp(), "nope.py")) == []
