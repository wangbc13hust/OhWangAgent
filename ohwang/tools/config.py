from __future__ import annotations

from ..services import load_settings, save_settings, update_settings
from .base import BaseTool, ToolResult


class ConfigTool(BaseTool):
    name = "config"
    description = (
        "Read or update permission rules in .ohwang/settings.json. "
        "Actions: 'list' (all rules), 'get' (one section or rule), "
        "'allow'|'ask'|'deny' (add a tool name/glob to that section), "
        "'remove' (drop a rule). Rules persist across sessions."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get", "allow", "ask", "deny", "remove"],
            },
            "key": {
                "type": "string",
                "description": "Tool name or glob pattern (e.g. 'bash', 'mcp__*').",
            },
        },
        "required": ["action"],
    }
    default_permission = "ask"
    # These actions never mutate state — they may run even in read-only PLAN mode.
    read_only_actions = ("list", "get")

    def __init__(self, workdir, permissions=None) -> None:
        self._workdir = workdir
        self._permissions = permissions

    def execute(self, input: dict) -> ToolResult:
        action = input["action"]
        key = input.get("key", "")

        if action == "list":
            settings = load_settings(self._workdir)
            lines = ["Permission rules:"]
            for section in ("allow", "ask", "deny"):
                rules = settings.get(section, [])
                lines.append(f"  {section}: {', '.join(rules) if rules else '(none)'}")
            return ToolResult(content="\n".join(lines))

        if action == "get":
            if not key:
                return ToolResult(
                    content="get requires 'key' (tool name/glob or 'allow'/'ask'/'deny').",
                    is_error=True,
                )
            settings = load_settings(self._workdir)
            if key in ("allow", "ask", "deny"):
                rules = settings.get(key, [])
                return ToolResult(content=f"{key}: {', '.join(rules) if rules else '(none)'}")
            for section in ("allow", "ask", "deny"):
                if key in settings.get(section, []):
                    return ToolResult(content=f"{key} is {section}.")
            return ToolResult(content=f"{key} has no rule (uses tool default).")

        if action in ("allow", "ask", "deny") and not key:
            return ToolResult(content=f"{action} requires 'key'.", is_error=True)

        try:
            settings = update_settings(self._workdir, action, key, "")
        except ValueError as exc:
            return ToolResult(content=str(exc), is_error=True)

        if self._permissions is not None:
            self._permissions._allow = list(settings["allow"])
            self._permissions._ask_list = list(settings["ask"])
            self._permissions._deny = list(settings["deny"])

        return ToolResult(content=f"Updated {action} '{key}'.")
