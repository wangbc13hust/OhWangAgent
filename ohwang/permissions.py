from __future__ import annotations

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
    """Decides whether a tool call may run, mode-aware.

    Modes:
      DEFAULT — per-tool default_permission, ask callback for "ask" tools
      PLAN    — read-only: only "allow" tools pass (writes/bash blocked)
      AUTO    — auto-approve everything
      BYPASS  — no checks at all
    """

    def __init__(
        self,
        auto_approve: bool = False,
        ask_callback: Optional[AskCallback] = None,
        rules: Optional[dict[str, str]] = None,
        mode: Optional[Mode] = None,
    ) -> None:
        self._ask = ask_callback
        self._rules: dict[str, str] = rules or {}
        self._always_allow: set[str] = set()
        self.mode = mode if mode is not None else (Mode.AUTO if auto_approve else Mode.DEFAULT)

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
        if tool.name in self._rules:
            return PermissionDecision(self._rules[tool.name])
        return PermissionDecision(tool.default_permission)

    def can_run(self, tool: BaseTool, input: dict) -> bool:
        if self.mode is Mode.BYPASS:
            return True
        if self.mode is Mode.PLAN:
            return tool.default_permission == "allow"
        if self.mode is Mode.AUTO:
            return True

        if self._signature(tool.name, input) in self._always_allow:
            return True
        decision = self.decide(tool, input)
        if decision is PermissionDecision.ALLOW:
            return True
        if decision is PermissionDecision.DENY:
            return False
        if self._ask is None:
            return False
        answer = self._ask(tool.name, input)
        if answer == "always":
            self._always_allow.add(self._signature(tool.name, input))
            return True
        return answer == "allow"
