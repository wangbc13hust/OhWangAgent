from ohwang.tools.powershell import PowerShellTool
from ohwang.tools.shell_output import truncate


def test_truncate_keeps_ends():
    text = "a" * 100
    out = truncate(text, limit=20)
    assert out.startswith("a" * 10)
    assert out.endswith("a" * 10)
    assert "truncated" in out


def test_truncate_short_text_unchanged():
    text = "short"
    assert truncate(text, limit=20) == "short"


def test_execute_runs_powershell():
    tool = PowerShellTool()
    result = tool.execute({"command": "Write-Output 'hello ps'"})
    assert not result.is_error
    assert "hello ps" in result.content
    assert "[exit code 0]" in result.content


def test_execute_timeout():
    tool = PowerShellTool()
    result = tool.execute({"command": "Start-Sleep -Seconds 5", "timeout": 1})
    assert result.is_error
    assert "timed out" in result.content


def test_execute_error_reports_nonzero():
    tool = PowerShellTool()
    result = tool.execute({"command": "Write-Error 'boom'"})
    assert result.is_error
