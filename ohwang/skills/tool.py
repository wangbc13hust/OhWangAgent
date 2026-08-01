from __future__ import annotations

from typing import Optional

from ..tools.base import BaseTool, ToolResult
from .loader import Skill, SkillLoader


class SkillTool(BaseTool):
    """Invoke a named skill: injects its prompt and optionally restricts tools."""

    name = "skill"
    description = (
        "Load and invoke a named skill. A skill is a prompt template that "
        "specializes the agent for a particular workflow (debug, verify, "
        "simplify, etc.). Pass the skill name and any context."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name (e.g. 'debug', 'verify').",
            },
            "context": {
                "type": "string",
                "description": "Additional context to append to the skill prompt.",
            },
        },
        "required": ["name"],
    }
    default_permission = "allow"

    def __init__(self, loader: SkillLoader) -> None:
        self._loader = loader

    def execute(self, input: dict) -> ToolResult:
        name = input["name"]
        context = input.get("context", "")

        skill = self._loader.get(name)
        if skill is None:
            available = ", ".join(self._loader.list_names()) or "(none)"
            return ToolResult(
                content=f"Unknown skill: {name}. Available: {available}",
                is_error=True,
            )

        prompt = skill.prompt
        if context:
            prompt += f"\n\n# Context\n{context}"

        meta = f"Skill: {skill.name} ({skill.source})"
        if skill.tools:
            meta += f"\nAllowed tools: {', '.join(skill.tools)}"

        return ToolResult(content=f"{meta}\n\n{prompt}")
