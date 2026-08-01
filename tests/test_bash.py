import sys

import pytest

from ohwang.tools.bash import BashTool


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


def test_bash_truncate():
    text = "x" * 100
    out = BashTool._truncate(text, limit=20)
    assert "truncated" in out
    assert len(out) < len(text)


def test_bash_truncate_short_text_unchanged():
    assert BashTool._truncate("short", limit=20) == "short"
