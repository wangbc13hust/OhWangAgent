"""Built-in safety guards for the agent loop.

Currently: dangerous shell command patterns. A pre_tool_use handler scans
bash/powershell commands for destructive operations (rm -rf on root/home or
system dirs, git force-push, disk formatting, fork bombs, ...) and blocks them
before they can run — the mirror of Claude Code's confirm-on-dangerous-command
behavior, implemented as pure pattern matching with no permission-mode coupling.

Patterns are word/context bounded so benign uses (`rm -rf ./build/tmp`, a
commit message mentioning "--force") are not caught. The guard is a hard block
with no bypass: the model receives "Blocked by hook: ..." and can adapt.
"""

from __future__ import annotations

import re
from typing import Optional

# (compiled regex, human-readable description). Matched with re.search against
# the whole command string, case-insensitively.
DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    # rm -rf against catastrophic targets: /, /*, ~, $HOME, or a whole
    # system/user directory (/home /Users /etc /usr). Subpaths (/home/user,
    # /tmp/build, ~/projects) are allowed.
    (
        re.compile(
            r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*[rf]\b"
            r"(?:\s+--no-preserve-root)?\s+"
            r"(?:/|/?\*|~|\$HOME|/(?:home|Users|etc|usr))(?:\s|$)"
        ),
        "destructive rm -rf (root/home/system dir)",
    ),
    (re.compile(r"\bgit\s+push\b[^|;&\n]*\s+(?:-f|--force)\b"), "git push --force"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bgit\s+clean\s+-[a-z]*[fd][a-z]*"), "git clean -fd"),
    (re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b"), "filesystem formatting"),
    (re.compile(r"\bformat\s+[a-zA-Z]:\s*"), "drive format (Windows)"),
    (re.compile(r"\bdd\b[^|;&\n]*\bof=/dev/sd[a-z]"), "dd write to raw device"),
    (
        re.compile(r"(?:^|[;&|]\s*)\b(?:shutdown|reboot|halt|poweroff)\b"),
        "system shutdown/reboot",
    ),
    (re.compile(r":\s*\(\s*\)\s*\{"), "fork bomb"),
    (
        re.compile(r"\b(?:rmdir|rd)\s+/[a-z]*s[a-z]*(?:\s+/[a-z]*q[a-z]*)?\s+[a-zA-Z]:\\"),
        "recursive directory delete (Windows)",
    ),
    (re.compile(r"\bdel\s+/[a-z]*s[a-z]*\b"), "recursive file delete (Windows)"),
]

# Tools whose "command" input the guard inspects.
_SHELL_TOOLS = ("bash", "powershell")


def dangerous_command_hook(name: str, input: dict) -> Optional[dict]:
    """pre_tool_use handler: block destructive shell commands.

    Returns None to allow, or {"block": True, "reason": ...} to deny.
    """
    if name not in _SHELL_TOOLS:
        return None
    command = input.get("command", "")
    if not isinstance(command, str):
        return None
    for pattern, description in DANGEROUS_PATTERNS:
        if pattern.search(command):
            return {
                "block": True,
                "reason": f"Dangerous command pattern: {description}",
            }
    return None
