from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    prompt: str
    tools: list[str] = field(default_factory=list)
    source: str = ""


class SkillLoader:
    """Load skills from .ohwang/skills/*.json and bundled skills.

    Skill JSON schema:
      {
        "name": "debug",
        "description": "Debug a failing test",
        "prompt": "Analyze the failing test and suggest fixes...",
        "tools": ["bash", "file_read", "grep", "glob"]
      }
    """

    BUNDLED_DIR = Path(__file__).parent / "bundled"

    def __init__(self, workdir: str | Path) -> None:
        self.user_dir = Path(workdir) / ".ohwang" / "skills"
        self._skills: dict[str, Skill] = {}

    def load_all(self) -> dict[str, Skill]:
        self._skills.clear()
        self._load_dir(self.BUNDLED_DIR, source="bundled")
        self._load_dir(self.user_dir, source="user")
        return self._skills

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_names(self) -> list[str]:
        return list(self._skills)

    def _load_dir(self, path: Path, source: str) -> None:
        if not path.is_dir():
            return
        for f in sorted(path.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = data.get("name", f.stem)
            self._skills[name] = Skill(
                name=name,
                description=data.get("description", ""),
                prompt=data.get("prompt", ""),
                tools=data.get("tools", []),
                source=source,
            )
