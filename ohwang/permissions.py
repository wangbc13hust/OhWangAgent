from __future__ import annotations

from enum import Enum
from typing import Callable, Optional

from .tools.base import BaseTool


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


AskCallback = Callable[[str, dict], str]


class PermissionManager:
    """Decides whether a tool call may run.

    default_permission on each tool: "allow" (read-only/safe), "ask", "deny".
    The CLI injects an ask_callback returning "allow" | "deny" | "always".
    """

    def __init__(
        self,
        auto_approve: bool = False,
        ask_callback: Optional[AskCallback] = None,
        rules: Optional[dict[str, str]] = None,
    ) -> None:
        self.auto_approve = auto_approve
        self._ask = ask_callback
        self._rules: dict[str, str] = rules or {}
        self._always_allow: set[str] = set()

    def _signature(self, tool_name: str, input: dict) -> str:
        key_arg = input.get("file_path") or input.get("command") or ""
        return f"{tool_name}::{key_arg}"

    def decide(self, tool: BaseTool, input: dict) -> PermissionDecision:
        if tool.name in self._rules:
            return PermissionDecision(self._rules[tool.name])
        return PermissionDecision(tool.default_permission)

    def can_run(self, tool: BaseTool, input: dict) -> bool:
        if self.auto_approve:
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
