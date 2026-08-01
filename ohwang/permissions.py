from __future__ import annotations

import fnmatch
from enum import Enum
from typing import Callable, Optional

from .modes import Mode
from .tools.base import BaseTool


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


AskCallback = Callable[[str, dict], str]


class PermissionManager:
    """Decides whether a tool call may run, mode-aware and rule-aware.

    Modes:
      DEFAULT — per-tool default_permission, ask callback for "ask" tools
      PLAN    — read-only: only "allow" tools pass (writes/bash blocked)
      AUTO    — auto-approve everything
      BYPASS  — no checks at all

    Rules (from .ohwang/settings.json):
      allow/ask/deny are lists of tool names or glob patterns (e.g. "mcp__*").
    """

    def __init__(
        self,
        auto_approve: bool = False,
        ask_callback: Optional[AskCallback] = None,
        rules: Optional[dict[str, str]] = None,
        mode: Optional[Mode] = None,
        allow: Optional[list[str]] = None,
        ask: Optional[list[str]] = None,
        deny: Optional[list[str]] = None,
    ) -> None:
        self._ask = ask_callback
        self._rules: dict[str, str] = rules or {}
        self._allow: list[str] = list(allow or [])
        self._ask_list: list[str] = list(ask or [])
        self._deny: list[str] = list(deny or [])
        self._always_allow: set[str] = set()
        self.mode = mode if mode is not None else (Mode.AUTO if auto_approve else Mode.DEFAULT)
        self._plan_prev: Optional[Mode] = None

    @property
    def auto_approve(self) -> bool:
        return self.mode in (Mode.AUTO, Mode.BYPASS)

    @auto_approve.setter
    def auto_approve(self, value: bool) -> None:
        if value:
            if self.mode is Mode.DEFAULT:
                self.mode = Mode.AUTO
        else:
            if self.mode in (Mode.AUTO, Mode.BYPASS):
                self.mode = Mode.DEFAULT

    def _signature(self, tool_name: str, input: dict) -> str:
        key_arg = input.get("file_path") or input.get("command") or ""
        return f"{tool_name}::{key_arg}"

    def decide(self, tool: BaseTool, input: dict) -> PermissionDecision:
        name = tool.name
        if any(fnmatch.fnmatch(name, p) for p in self._deny):
            return PermissionDecision.DENY
        if any(fnmatch.fnmatch(name, p) for p in self._allow):
            return PermissionDecision.ALLOW
        if any(fnmatch.fnmatch(name, p) for p in self._ask_list):
            return PermissionDecision.ASK
        if name in self._rules:
            return PermissionDecision(self._rules[name])
        return PermissionDecision(tool.default_permission)

    def can_run(self, tool: BaseTool, input: dict) -> bool:
        if self.mode is Mode.BYPASS:
            return True
        if self.mode is Mode.PLAN:
            return tool.default_permission == "allow"
        if self.mode is Mode.AUTO:
            return True

        decision = self.decide(tool, input)
        # deny rules always win — even over a remembered "always" grant.
        if decision is PermissionDecision.DENY:
            return False
        if self._signature(tool.name, input) in self._always_allow:
            return True
        if decision is PermissionDecision.ALLOW:
            return True
        if self._ask is None:
            return False
        answer = self._ask(tool.name, input)
        if answer == "always":
            self._always_allow.add(self._signature(tool.name, input))
            return True
        return answer == "allow"
