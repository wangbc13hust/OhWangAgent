from ohwang.services.lsp import (
    LSPClient,
    _path_to_uri,
    _guess_language,
    _severity_name,
    _read_file,
)
from ohwang.tools.lsp_diagnose import LSPDiagnoseTool
import tempfile
import os


def test_path_to_uri():
    uri = _path_to_uri("C:/Users/test/project/file.py")
    assert uri.startswith("file:///")
    assert "file.py" in uri


def test_guess_language():
    assert _guess_language("app.py") == "python"
    assert _guess_language("app.ts") == "typescript"
    assert _guess_language("app.tsx") == "typescriptreact"
    assert _guess_language("app.js") == "javascript"
    assert _guess_language("app.go") == "go"
    assert _guess_language("app.rs") == "rust"
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
