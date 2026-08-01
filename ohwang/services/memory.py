from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class MemoryStore:
    """Persistent project memory stored in .ohwang/memory/.

    Two layers:
      1. CLAUDE.md / AGENTS.md in the project root — loaded as context.
      2. .ohwang/memory/facts.json — structured facts with relevance search.
    """

    def __init__(self, workdir: str | Path) -> None:
        self.workdir = Path(workdir)
        self.memory_dir = self.workdir / ".ohwang" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def load_project_context(self) -> str:
        """Load CLAUDE.md / AGENTS.md from project root as context string."""
        for name in ("CLAUDE.md", "AGENTS.md"):
            path = self.workdir / name
            if path.is_file():
                try:
                    return path.read_text(encoding="utf-8")
                except Exception:
                    continue
        return ""

    def add_fact(self, key: str, value: str, tags: Optional[list[str]] = None) -> None:
        """Add or update a fact in the memory store."""
        facts = self._load_facts()
        facts[key] = {
            "value": value,
            "tags": list(tags or []),
        }
        self._save_facts(facts)

    def get_fact(self, key: str) -> Optional[str]:
        facts = self._load_facts()
        entry = facts.get(key)
        return entry["value"] if entry else None

    def search_facts(self, query: str) -> list[dict]:
        """Simple keyword search over fact keys, values, and tags."""
        facts = self._load_facts()
        query_lower = query.lower()
        results: list[dict] = []
        for key, entry in facts.items():
            value = entry.get("value", "")
            tags = entry.get("tags", [])
            searchable = f"{key} {value} {' '.join(tags)}".lower()
            if query_lower in searchable:
                results.append({"key": key, "value": value, "tags": tags})
        return results

    def list_facts(self) -> list[dict]:
        facts = self._load_facts()
        return [
            {"key": k, "value": v.get("value", ""), "tags": v.get("tags", [])}
            for k, v in facts.items()
        ]

    def delete_fact(self, key: str) -> bool:
        facts = self._load_facts()
        if key not in facts:
            return False
        del facts[key]
        self._save_facts(facts)
        return True

    def render_context(self) -> str:
        """Build a context string combining project markdown + relevant facts."""
        parts: list[str] = []
        project_ctx = self.load_project_context()
        if project_ctx:
            parts.append(project_ctx)

        facts = self.list_facts()
        if facts:
            parts.append("\n# Project Memory\n")
            for f in facts:
                tags_str = f" [{', '.join(f['tags'])}]" if f["tags"] else ""
                parts.append(f"- **{f['key']}**{tags_str}: {f['value']}")

        return "\n".join(parts)

    def _load_facts(self) -> dict:
        path = self.memory_dir / "facts.json"
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_facts(self, facts: dict) -> None:
        path = self.memory_dir / "facts.json"
        path.write_text(
            json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
