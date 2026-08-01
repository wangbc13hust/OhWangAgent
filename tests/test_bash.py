import sys

import pytest

from ohwang.tools.bash import BashTool
from ohwang.tools.shell_output import command_result, decode_output, truncate


def test_decode_output_utf8():
    assert decode_output("中文内容".encode("utf-8")) == "中文内容"


def test_decode_output_invalid_bytes_fallback():
    out = decode_output(b"\xff\xfe broken")
    assert isinstance(out, str)
    assert "broken" in out


def test_decode_output_empty():
    assert decode_output(b"") == ""


def test_bash_executes_command():
    r = BashTool().execute({"command": "echo hello-bash"})
    assert not r.is_error
    assert "hello-bash" in r.content
    assert "[exit code 0]" in r.content


def test_bash_error_exit_code():
    r = BashTool().execute({"command": "exit 3"})
    assert r.is_error
    assert "[exit code 3]" in r.content


def test_bash_stderr_merged():
    r = BashTool().execute({"command": "echo out && echo err 1>&2"})
    assert not r.is_error
    assert "out" in r.content
    assert "err" in r.content


@pytest.mark.skipif(sys.platform != "win32", reason="uses Windows cmd ping")
def test_bash_timeout():
    r = BashTool().execute({"command": "ping -n 6 127.0.0.1 >nul", "timeout": 1})
    assert r.is_error
    assert "timed out" in r.content


def test_truncate_keeps_ends():
    text = "x" * 100
    out = truncate(text, limit=20)
    assert "truncated" in out
    assert len(out) < len(text)
    assert out.startswith("x" * 10)
    assert out.endswith("x" * 10)


def test_truncate_short_text_unchanged():
    assert truncate("short", limit=20) == "short"


def test_command_result_success():
    r = command_result("out", "err", 0)
    assert not r.is_error
    assert "out" in r.content
    assert "err" in r.content
    assert "[exit code 0]" in r.content


def test_command_result_nonzero():
    r = command_result("", "", 3)
    assert r.is_error
    assert "[exit code 3]" in r.content


def test_command_result_timeout():
    r = command_result("", "", 0, timed_out=True, timeout=1)
    assert r.is_error
    assert "timed out" in r.content
