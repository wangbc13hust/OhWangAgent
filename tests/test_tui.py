import ast
from pathlib import Path

import pytest

from ohwang.tui.render import Renderer, read_stdin_line

_ROOT = Path(__file__).resolve().parent.parent


def _make_renderer():
    renderer = Renderer()
    renderer.console = _RecordConsole()
    return renderer


class _RecordConsole:
    def __init__(self):
        self.record = True
        self.text = ""

    def print(self, message, **kwargs):
        self.text += str(message) + "\n"

    def export_text(self):
        return self.text


def test_tui_widget_no_undefined_chat_refs():
    src = (_ROOT / "ohwang/tui/widgets/app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id == "ChatLog":
                raise AssertionError(
                    "tui app.py references undefined ChatLog (class is ChatPanel)"
                )

    assert "ChatPanel" in defined


def test_renderer_info_escapes_markup():
    renderer = _make_renderer()
    renderer.info("[/dim] injected [bold] tag")
    assert "[/dim]" in renderer.console.export_text()


def test_renderer_warn_escapes_markup():
    renderer = _make_renderer()
    renderer.warn("[red]x[/red] <danger>")
    assert "[red]" in renderer.console.export_text()


def test_renderer_tool_call_escapes_input():
    renderer = _make_renderer()
    renderer.tool_call({"name": "bash", "input": {"command": "echo [red]"}})
    assert "[red]" in renderer.console.export_text()


def test_renderer_ask_question_escapes_labels(monkeypatch):
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **k: "1")
    renderer = _make_renderer()
    renderer.ask_question("[bold]?[/bold]", [{"label": "a[/b]", "description": "[x]"}])
    text = renderer.console.export_text()
    assert "\\[x]" in text
    assert "a\\[/b]" in text
    assert "[x]" not in text.replace("\\[x]", "")
    assert "[/b]" not in text.replace("\\[/b]", "")


def test_renderer_info_without_markup_plain():
    renderer = _make_renderer()
    renderer.info("just text")
    assert "just text" in renderer.console.export_text()


def test_renderer_ask_defaults_to_deny_on_eof(monkeypatch):
    def _raise_eof(*a, **k):
        raise EOFError

    monkeypatch.setattr("rich.prompt.Prompt.ask", _raise_eof)
    renderer = _make_renderer()
    assert renderer.ask("bash", {"command": "x"}) == "deny"


def test_renderer_ask_question_defaults_on_eof(monkeypatch):
    def _raise_eof(*a, **k):
        raise EOFError

    monkeypatch.setattr("rich.prompt.Prompt.ask", _raise_eof)
    renderer = _make_renderer()
    assert renderer.ask_question("pick one", [{"label": "a"}]) == "1"


def test_read_stdin_line_utf8_bytes(monkeypatch):
    class _Buf:
        def readline(self):
            return "中文内容\r\n".encode("utf-8")

    class _Stdin:
        buffer = _Buf()

    monkeypatch.setattr("ohwang.tui.render.sys.stdin", _Stdin())
    assert read_stdin_line() == "中文内容"


def test_read_stdin_line_gbk_bytes(monkeypatch):
    class _Buf:
        def readline(self):
            return "中文内容\r\n".encode("gbk")

    class _Stdin:
        buffer = _Buf()

    monkeypatch.setattr("ohwang.tui.render.sys.stdin", _Stdin())
    assert read_stdin_line() == "中文内容"


def test_read_stdin_line_eof(monkeypatch):
    class _Buf:
        def readline(self):
            return b""

    class _Stdin:
        buffer = _Buf()

    monkeypatch.setattr("ohwang.tui.render.sys.stdin", _Stdin())
    with pytest.raises(EOFError):
        read_stdin_line()


def test_read_stdin_line_strips_utf8_bom(monkeypatch):
    class _Buf:
        def readline(self):
            return b"\xef\xbb\xbf/exit\r\n"

    class _Stdin:
        buffer = _Buf()

    monkeypatch.setattr("ohwang.tui.render.sys.stdin", _Stdin())
    assert read_stdin_line() == "/exit"


def test_stream_text_small_chunks_buffered(monkeypatch):
    out = []
    monkeypatch.setattr("ohwang.tui.render.sys.stdout", _Capture(out))
    r = _make_renderer()
    r._flush_every = 999.0
    r.stream_text("abc")
    r.stream_text("def")
    assert out == []


def test_stream_text_sentence_end_flushes(monkeypatch):
    out = []
    monkeypatch.setattr("ohwang.tui.render.sys.stdout", _Capture(out))
    r = _make_renderer()
    r._flush_every = 999.0
    r.stream_text("hello.")
    assert out == ["hello."]


def test_stream_text_big_chunk_flushes(monkeypatch):
    out = []
    monkeypatch.setattr("ohwang.tui.render.sys.stdout", _Capture(out))
    r = _make_renderer()
    r._flush_every = 999.0
    r.stream_text("x" * 300)
    assert out == ["x" * 300]


def test_tool_call_adds_newline_before(monkeypatch):
    out = []
    monkeypatch.setattr("ohwang.tui.render.sys.stdout", _Capture(out))
    r = _make_renderer()
    r._flush_every = 999.0
    r.stream_text("thinking")
    r.tool_call({"name": "bash", "input": {"command": "ls"}})
    written = "".join(out)
    assert written.endswith("thinking\n")


def test_end_turn_flushes_pending(monkeypatch):
    out = []
    monkeypatch.setattr("ohwang.tui.render.sys.stdout", _Capture(out))
    r = _make_renderer()
    r._flush_every = 999.0
    r.stream_text("pending")
    r.end_turn()
    assert "pending" in "".join(out)


class _Capture:
    def __init__(self, sink):
        self._sink = sink

    def write(self, s):
        self._sink.append(s)

    def flush(self):
        pass
