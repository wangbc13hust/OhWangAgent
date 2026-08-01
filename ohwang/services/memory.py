from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_MEMORY_EXTRACTION_PROMPT = """You are a memory extraction service. Analyze the conversation and
extract up to 10 durable facts worth remembering across sessions. Focus on:
project decisions, conventions, user preferences, key parameters, and gotchas.
Do NOT include one-off, trivial, or already-known facts.
Return ONLY a JSON array, no markdown, no commentary:
[{"key": "short_snake_key", "value": "one sentence fact", "tags": ["decision"]}]
If nothing is worth saving, return [].
"""


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
        self._facts_path = self.memory_dir / "facts.json"
        self._facts_cache: dict | None = None
        self._facts_mtime: float | None = None
        self._ctx_cache: str | None = None
        self._ctx_sig: tuple | None = None
        self._context_cache: str | None = None
        self._context_sig: tuple | None = None
        self._max_facts_in_context = 30

    def load_project_context(self) -> str:
        """Load CLAUDE.md / AGENTS.md from project root as context string."""
        sig = self._project_sig()
        if self._ctx_cache is not None and sig == self._ctx_sig:
            return self._ctx_cache
        text = ""
        for name in ("CLAUDE.md", "AGENTS.md"):
            path = self.workdir / name
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                break
        self._ctx_cache = text
        self._ctx_sig = sig
        return text

    def _project_sig(self) -> tuple:
        sig = []
        for name in ("CLAUDE.md", "AGENTS.md"):
            path = self.workdir / name
            if path.is_file():
                try:
                    sig.append((name, path.stat().st_mtime, path.stat().st_size))
                except OSError:
                    sig.append((name, None, None))
            else:
                sig.append((name, None, None))
        return tuple(sig)

    def _facts_signature(self) -> object:
        try:
            return self._facts_path.stat().st_mtime
        except OSError:
            return None

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
        sig = (self._project_sig(), self._facts_signature())
        if self._context_cache is not None and sig == self._context_sig:
            return self._context_cache
        parts: list[str] = []
        project_ctx = self.load_project_context()
        if project_ctx:
            parts.append(project_ctx)

        facts = self.list_facts()
        if facts:
            parts.append("\n# Project Memory\n")
            shown = facts[-self._max_facts_in_context :]
            if len(facts) > len(shown):
                parts.append(
                    f"(showing {len(shown)} of {len(facts)} facts; use memory_read for the rest)\n"
                )
            for f in shown:
                tags_str = f" [{', '.join(f['tags'])}]" if f["tags"] else ""
                parts.append(f"- **{f['key']}**{tags_str}: {f['value']}")

        self._context_cache = "\n".join(parts)
        self._context_sig = sig
        return self._context_cache

    def _invalidate_context(self) -> None:
        self._context_cache = None
        self._context_sig = None

    def _load_facts(self) -> dict:
        if not self._facts_path.is_file():
            self._facts_cache = {}
            self._facts_mtime = None
            return {}
        try:
            mtime = self._facts_path.stat().st_mtime
        except OSError:
            return self._facts_cache or {}
        if self._facts_cache is not None and mtime == self._facts_mtime:
            return self._facts_cache
        try:
            data = json.loads(self._facts_path.read_text(encoding="utf-8-sig"))
        except Exception:
            data = {}
        self._facts_cache = data
        self._facts_mtime = mtime
        return data

    def _save_facts(self, facts: dict) -> None:
        self._facts_path.write_text(
            json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._facts_cache = None
        self._facts_mtime = None
        self._invalidate_context()

    def import_facts(self, facts: list[dict]) -> int:
        """Merge extracted facts into the store. Returns the number added."""
        added = 0
        for f in facts:
            key = str(f.get("key", "")).strip()
            value = str(f.get("value", "")).strip()
            if not key or not value:
                continue
            tags = [str(t) for t in f.get("tags", []) if str(t).strip()]
            if self.get_fact(key) != value:
                self.add_fact(key, value, tags)
                added += 1
        return added


class MemoryExtractor:
    """Auto-extract durable facts from a conversation via the provider.

    `maybe_extract` only re-runs after the conversation grows by
    `growth_threshold` messages since the last extraction.
    """

    def __init__(self, store: MemoryStore, growth_threshold: int = 10) -> None:
        self._store = store
        self._growth_threshold = growth_threshold
        self._last_count = 0

    def extract(self, provider, messages: list[dict]) -> "int | None":
        """Ask the provider to summarize facts and persist them.

        Returns None when the provider call itself failed, so callers can
        distinguish "nothing worth saving" from "could not extract".
        """
        try:
            text_parts: list[str] = []
            for event in provider.chat(
                system=_MEMORY_EXTRACTION_PROMPT,
                messages=list(messages)[-30:],
                tools=[],
                max_tokens=2000,
            ):
                if event.get("type") == "text":
                    text_parts.append(event["text"])
            payload = "".join(text_parts)
        except Exception:
            return None

        facts = self._parse(payload)
        return self._store.import_facts(facts)

    def maybe_extract(self, provider, messages: list[dict]) -> int:
        if len(messages) - self._last_count < self._growth_threshold:
            return 0
        added = self.extract(provider, messages)
        if added is None:  # extraction failed (e.g. network) — don't advance
            return 0
        self._last_count = len(messages)
        return added

    @staticmethod
    def _parse(payload: str) -> list[dict]:
        payload = payload.strip()
        if not payload:
            return []
        if payload.startswith("```"):
            payload = payload.strip("`")
            payload = payload.removeprefix("json").strip()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            start, end = payload.find("["), payload.rfind("]")
            if start == -1 or end == -1:
                return []
            try:
                data = json.loads(payload[start : end + 1])
            except json.JSONDecodeError:
                return []
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, dict)]
