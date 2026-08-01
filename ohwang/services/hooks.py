from __future__ import annotations

import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Callable, Optional

_PRE = "pre_tool_use"
_POST = "post_tool_use"
_NOTIF = "notif"
EVENTS = (_PRE, _POST, _NOTIF)

PreToolHandler = Callable[[str, dict], Optional[dict | bool]]


class HookManager:
    """Lifecycle hooks: pre_tool_use / post_tool_use / notif.

    Two handler types:
      - Python callables registered via `register(event, fn)`.
      - Commands from `.ohwang/hooks.json`:
          {
            "pre_tool_use": [{"tool": "bash", "command": "python deny.py"}],
            "notif": [{"command": "powershell -Command ..."}]
          }
        For pre_tool_use, a non-zero exit code blocks the tool; stdout is the
        reason shown to the model.
    """

    def __init__(self, workdir: str | Path | None = None) -> None:
        self.workdir = Path(workdir) if workdir else None
        self._handlers: dict[str, list[PreToolHandler]] = {e: [] for e in EVENTS}
        self._cmds: dict[str, list[dict]] = {e: [] for e in EVENTS}

    def register(self, event: str, handler: PreToolHandler) -> None:
        if event not in EVENTS:
            raise ValueError(f"unknown hook event: {event}")
        self._handlers[event].append(handler)

    def load_json(self) -> int:
        if self.workdir is None:
            return 0
        path = self.workdir / ".ohwang" / "hooks.json"
        if not path.is_file():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        loaded = 0
        for event in EVENTS:
            for entry in data.get(event, []) or []:
                if isinstance(entry, dict) and entry.get("command"):
                    self._cmds[event].append(
                        {"tool": entry.get("tool"), "command": entry["command"]}
                    )
                    loaded += 1
        return loaded

    def run_pre_tool(self, name: str, input: dict) -> tuple[bool, str, dict]:
        """Return (allowed, reason, effective_input)."""
        for cb in self._handlers[_PRE]:
            result = cb(name, input)
            if result is False:
                return False, "blocked by hook", input
            if isinstance(result, dict):
                if result.get("block"):
                    return False, result.get("reason", "blocked by hook"), input
                if "input" in result:
                    input = result["input"]
        for entry in self._cmds[_PRE]:
            if entry.get("tool") and not fnmatch.fnmatch(name, entry["tool"]):
                continue
            code, out = self._run_cmd(entry["command"])
            if code != 0:
                reason = out.strip() or "blocked by pre_tool_use hook"
                return False, reason, input
        return True, "", input

    def run_post_tool(self, name: str, result_block: dict) -> None:
        for cb in self._handlers[_POST]:
            try:
                cb(name, result_block)
            except Exception:
                continue
        for entry in self._cmds[_POST]:
            if entry.get("tool") and not fnmatch.fnmatch(name, entry["tool"]):
                continue
            self._run_cmd(entry["command"])

    def notify(self, message: str) -> None:
        for cb in self._handlers[_NOTIF]:
            try:
                cb(message)
            except Exception:
                continue
        for entry in self._cmds[_NOTIF]:
            self._run_cmd(entry["command"])

    @staticmethod
    def _run_cmd(command: str) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except Exception as exc:
            return 1, f"hook command failed: {exc}"
