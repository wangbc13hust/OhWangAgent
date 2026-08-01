from __future__ import annotations

import json
import re
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
    path: str = ""


def _parse_scalar(raw: str):
    """Parse a single YAML-ish scalar (string, bool, int, float)."""
    raw = raw.strip()
    if not raw:
        return ""
    if raw == "~" or raw.lower() == "null":
        return None
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [
            _parse_scalar(item)
            for item in re.split(r",\s*", inner)
            if item.strip()
        ]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a SKILL.md-like file.

    Returns (frontmatter_dict, body). Uses a lightweight parser covering the
    common scalar/sequence subset; PyYAML is not a dependency.
    """
    text = text.lstrip("\ufeff").lstrip("\n")
    if not text.startswith("---"):
        return {}, text.strip()
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text.strip()

    fm: dict = {}
    key: Optional[str] = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("\t"):
            # continuation of a block-sequence list under the current key
            stripped = line.strip()
            if key is not None and stripped.startswith("- "):
                fm.setdefault(key, [])
                if isinstance(fm[key], list):
                    fm[key].append(_parse_scalar(stripped[2:]))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = _parse_scalar(value)
        if value is None or value == "":
            fm[key] = []
        elif isinstance(value, list):
            fm[key] = value
        else:
            fm[key] = value

    body = "\n".join(lines[end + 1 :]).strip()
    return fm, body


def _coerce_strings(values) -> list[str]:
    return [str(v) for v in values if v]


class SkillLoader:
    """Load skills from .ohwang/skills/ and bundled skills.

    Two formats are supported per directory:
      - Claude-Code style:  <name>/SKILL.md with YAML frontmatter
          ---
          name: debug
          description: Debug a failing test
          allowed-tools: [bash, file_read, grep, glob]
          ---
          <markdown instructions>
      - legacy JSON:        <name>.json
          {
            "name": "debug",
            "description": "...",
            "prompt": "...",
            "tools": ["bash"]
          }

    User skills live in <workdir>/.ohwang/skills/; bundled skills ship with the
    package. User skills with the same name override bundled ones.
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

    def describe_all(self) -> list[str]:
        """One-line descriptions for system-prompt injection.

        Returns lines like "- debug: Debug a failing test".
        """
        lines = []
        for name in sorted(self._skills):
            desc = self._skills[name].description.strip()
            if desc:
                lines.append(f"- {name}: {desc}")
        return lines

    def _load_dir(self, path: Path, source: str) -> None:
        if not path.is_dir():
            return

        # Claude-Code style: <name>/SKILL.md
        for sub in sorted(p for p in path.iterdir() if p.is_dir()):
            skill_md = sub / "SKILL.md"
            if skill_md.is_file():
                try:
                    skill = self._parse_skill_md(skill_md, source)
                except Exception:
                    continue
                if skill is not None:
                    self._skills[skill.name] = skill

        # legacy: <name>.json
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
                tools=_coerce_strings(data.get("tools", [])),
                source=source,
                path=str(f),
            )

    def _parse_skill_md(self, skill_md: Path, source: str) -> Optional[Skill]:
        fm, body = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        name = str(fm.get("name") or skill_md.parent.name)
        if not name or not body:
            return None
        tools = _coerce_strings(fm.get("allowed-tools", fm.get("tools", [])))
        return Skill(
            name=name,
            description=str(fm.get("description", "")),
            prompt=body,
            tools=tools,
            source=source,
            path=str(skill_md),
        )
