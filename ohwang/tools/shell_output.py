from __future__ import annotations

from .base import ToolResult


def truncate(text: str, limit: int = 20000) -> str:
    if len(text) <= limit:
        return text
    keep = limit // 2
    return (
        text[:keep]
        + f"\n... [truncated {len(text) - limit} chars] ...\n"
        + text[-keep:]
    )


def command_result(
    stdout: str,
    stderr: str,
    returncode: int,
    timed_out: bool = False,
    timeout: int = 120,
) -> ToolResult:
    """Build a ToolResult from subprocess output (shared by bash/powershell)."""
    if timed_out:
        return ToolResult(content=f"Command timed out after {timeout}s.", is_error=True)

    out = stdout or ""
    err = stderr or ""
    combined = out
    if err:
        combined += ("\n--- stderr ---\n" + err) if out else err

    combined = truncate(combined)
    header = f"[exit code {returncode}]\n"
    return ToolResult(content=header + combined, is_error=returncode != 0)
