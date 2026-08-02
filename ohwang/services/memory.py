from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

_MEMORY_EXTRACTION_PROMPT = """You are a memory extraction service. Analyze the conversation and
extract up to 10 durable facts worth remembering across sessions. Focus on:
project decisions, conventions, user preferences, key parameters, and gotchas.

Classify EVERY fact into exactly ONE of these types:
- "user"      - a durable preference or identity fact about the human user
                (e.g. "prefers Chinese replies", "uses Vim bindings", "works
                on the Payments team"). These go to global memory.
- "feedback"  - explicit praise or criticism of the assistant's output that
                should adjust future behavior (e.g. "user disliked verbose
                tool output").
- "project"   - a decision, convention, or parameter specific to THIS project
                (e.g. "auth uses JWT", "tests run with pytest -q").
- "reference" - an external pointer or location useful across sessions
                (e.g. "API docs live at ...", "bug tracker URL").

Do NOT include one-off, trivial, or already-known facts.
Explicitly EXCLUDE ephemeral content from a single session: meeting recaps,
raw data/figures from one extraction, one-off task details, or anything that
will not matter in future sessions. When in doubt, do not save it.

Return ONLY a JSON array, no markdown, no commentary:
[{"key": "short_snake_key", "value": "one sentence fact", "tags": ["decision"], "type": "project"}]
Every object MUST include a "type" field from the list above. If nothing is
worth saving, return [].
"""

_VALID_TYPES = ("user", "feedback", "project", "reference")


class MemoryStore:
    """Persistent project memory stored in .ohwang/memory/.

    Two layers:
      1. CLAUDE.md / AGENTS.md in the project root — loaded as context.
      2. .ohwang/memory/facts.json — structured facts with relevance search.

    A user (global) layer at `{home_dir}/.ohwang/memory/facts.json` can be
    enabled by passing `home_dir`. Facts carry a `type` field (user / feedback /
    project / reference); legacy rows without a type default to "project".
    """

    def __init__(self, workdir: str | Path, home_dir: Optional[str | Path] = None) -> None:
        self.workdir = Path(workdir)
        self.memory_dir = self.workdir / ".ohwang" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._facts_path = self.memory_dir / "facts.json"
        # User layer is lazily created on first write — never touch ~/.ohwang
        # merely for constructing a store (tests / build_agent stay clean).
        self._user_facts_path = (
            Path(home_dir) / ".ohwang" / "memory" / "facts.json"
            if home_dir
            else None
        )
        self._facts_cache: dict | None = None
        self._facts_mtime: float | None = None
        self._user_facts_cache: dict | None = None
        self._user_facts_mtime: float | None = None
        self._ctx_cache: str | None = None
        self._ctx_sig: tuple | None = None
        self._context_cache: str | None = None
        self._context_sig: tuple | None = None
        self._max_facts_in_context = 30
        self._max_ranked_facts = 10

    @property
    def user_layer_enabled(self) -> bool:
        return self._user_facts_path is not None

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

    def _facts_signature(self, scope: str = "project") -> object:
        path = self._user_facts_path if scope == "user" else self._facts_path
        if path is None:
            return None
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    def add_fact(
        self,
        key: str,
        value: str,
        tags: Optional[list[str]] = None,
        scope: str = "project",
        type_: Optional[str] = None,
    ) -> None:
        """Add or update a fact in the memory store.

        `scope="user"` writes to the global layer; if that layer is disabled it
        falls back to the project layer so the fact is never dropped.
        """
        if scope == "user" and self._user_facts_path is None:
            scope = "project"
        ftype = type_ or ("user" if scope == "user" else "project")
        facts = self._load_facts(scope)
        facts[key] = {
            "value": value,
            "tags": list(tags or []),
            "type": ftype,
        }
        self._save_facts(facts, scope)

    def get_fact(self, key: str, scope: str = "project") -> Optional[str]:
        facts = self._load_facts(scope)
        entry = facts.get(key)
        return entry["value"] if entry else None

    def search_facts(self, query: str, scope: Optional[str] = None) -> list[dict]:
        """Relevance-scored search over fact keys, values, and tags.

        `scope=None` merges both layers (project first, then user). Query tokens
        (whitespace-separated words, plus ASCII/underscore sub-tokens) match
        per-field with key > tags > value weighting, so a multi-word query like
        "key1 key2" hits a fact whose key is "key1". Results include the fact's
        `type`, best matches first.
        """
        if scope == "all":
            scope = None
        scored: list[tuple] = []
        for scope_name in ("project", "user"):
            if scope is not None and scope != scope_name:
                continue
            facts = self._load_facts(scope_name)
            for key, entry in facts.items():
                value = entry.get("value", "")
                tags = entry.get("tags", [])
                score = self._score_fact(
                    query,
                    str(key),
                    str(value),
                    " ".join(str(t) for t in tags),
                )
                if score > 0:
                    # `len(scored)` keeps insertion order (project facts first)
                    # as the tiebreak among equal scores.
                    scored.append(
                        (
                            score,
                            len(scored),
                            {
                                "key": key,
                                "value": value,
                                "tags": tags,
                                "type": entry.get("type", "project"),
                            },
                        )
                    )
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [f for _, _, f in scored]

    def list_facts(self, scope: Optional[str] = None) -> list[dict]:
        if scope == "all":
            scope = None
        results: list[dict] = []
        for scope_name in ("project", "user"):
            if scope is not None and scope != scope_name:
                continue
            facts = self._load_facts(scope_name)
            for k, v in facts.items():
                results.append(
                    {
                        "key": k,
                        "value": v.get("value", ""),
                        "tags": v.get("tags", []),
                        "type": v.get("type", "project"),
                    }
                )
        return results

    def delete_fact(self, key: str, scope: str = "project") -> bool:
        facts = self._load_facts(scope)
        if key not in facts:
            return False
        del facts[key]
        self._save_facts(facts, scope)
        return True

    def render_context(self, query: str = "") -> str:
        """Build a context string combining project markdown + relevant facts.

        An empty query renders the tail of each layer's facts (latest first,
        capped at `_max_facts_in_context`). A non-empty query switches to
        relevance-ranked rendering (`_render_ranked_context`).
        """
        if query:
            return self._render_ranked_context(query)
        sig = (
            self._project_sig(),
            self._facts_signature("project"),
            self._facts_signature("user"),
        )
        if self._context_cache is not None and sig == self._context_sig:
            return self._context_cache
        parts: list[str] = []
        project_ctx = self.load_project_context()
        if project_ctx:
            parts.append(project_ctx)

        user_facts = self.list_facts(scope="user")
        if user_facts:
            parts.append("\n# User Memory\n")
            shown = user_facts[-self._max_facts_in_context :]
            if len(user_facts) > len(shown):
                parts.append(
                    f"(showing {len(shown)} of {len(user_facts)} user facts; use memory_read for the rest)\n"
                )
            for f in shown:
                parts.append(self._format_fact(f))

        facts = self.list_facts(scope="project")
        if facts:
            parts.append("\n# Project Memory\n")
            shown = facts[-self._max_facts_in_context :]
            if len(facts) > len(shown):
                parts.append(
                    f"(showing {len(shown)} of {len(facts)} facts; use memory_read for the rest)\n"
                )
            for f in shown:
                parts.append(self._format_fact(f))

        self._context_cache = "\n".join(parts)
        self._context_sig = sig
        return self._context_cache

    def _render_ranked_context(self, query: str) -> str:
        """Relevance-ranked facts for a specific query (no caching, fresh)."""
        parts: list[str] = []
        project_ctx = self.load_project_context()
        if project_ctx:
            parts.append(project_ctx)
        facts = self._rank_facts(query, self.list_facts(scope=None))
        if facts:
            parts.append("\n# Memory\n")
            for f in facts:
                parts.append(self._format_fact(f))
        return "\n".join(parts)

    @staticmethod
    def _format_fact(f: dict) -> str:
        tags_str = f" [{', '.join(f['tags'])}]" if f["tags"] else ""
        return f"- **{f['key']}**{tags_str}: {f['value']}"

    @staticmethod
    def _score_fact(query: str, key: str, value: str, tags: str) -> float:
        """Relevance score of one fact against a query (higher = better).

        Whole-query substring hits carry the largest weight, preserving exact
        phrase and CJK whole-string matching. Then per-token hits — whitespace
        words (so "key1 key2" reaches a fact keyed "key1") and ASCII/underscore
        sub-tokens (so "cli.py" reaches "cli_runner") — apply field weights
        key > tags > value. Returns 0 when nothing hits.
        """
        q = query.strip().lower()
        if not q:
            return 0.0
        tokens = {t for t in q.split() if t} | {
            t for t in re.findall(r"[0-9a-zA-Z_]+", q) if t
        }
        score = 0.0
        if q in key:
            score += 8
        if q in tags:
            score += 5
        if q in value:
            score += 3
        for tok in tokens:
            if tok in key:
                score += 4
            elif tok in tags:
                score += 2
            elif tok in value:
                score += 1
        return score

    def _rank_facts(self, query: str, facts: list[dict]) -> list[dict]:
        """Deterministic relevance ranking — no LLM, no side queries.

        Delegates to the shared tokenized scorer (whole-phrase + per-token hits,
        key > tags > value), so the context-injection path benefits from the
        same multi-word/CJK matching as `search_facts`. Ties break by insertion
        order (= recency); results capped at `_max_ranked_facts`.
        """
        ranked: list[tuple] = []
        for idx, fact in enumerate(facts):
            score = self._score_fact(
                query,
                str(fact.get("key", "")),
                str(fact.get("value", "")),
                " ".join(str(t) for t in fact.get("tags", [])),
            )
            if score > 0:
                ranked.append((score, idx, fact))
        ranked.sort(key=lambda t: (-t[0], -t[1]))
        return [f for _, _, f in ranked][: self._max_ranked_facts]

    def _invalidate_context(self) -> None:
        self._context_cache = None
        self._context_sig = None

    def _load_facts(self, scope: str = "project") -> dict:
        if scope == "user":
            if self._user_facts_path is None:
                return {}
            path = self._user_facts_path
            if not path.is_file():
                self._user_facts_cache = {}
                self._user_facts_mtime = None
                return {}
            try:
                mtime = path.stat().st_mtime
            except OSError:
                return self._user_facts_cache or {}
            if (
                self._user_facts_cache is not None
                and mtime == self._user_facts_mtime
            ):
                return self._user_facts_cache
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                data = {}
            self._user_facts_cache = data
            self._user_facts_mtime = mtime
            return data

        path = self._facts_path
        if not path.is_file():
            self._facts_cache = {}
            self._facts_mtime = None
            return {}
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return self._facts_cache or {}
        if self._facts_cache is not None and mtime == self._facts_mtime:
            return self._facts_cache
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            data = {}
        self._facts_cache = data
        self._facts_mtime = mtime
        return data

    def _save_facts(self, facts: dict, scope: str = "project") -> None:
        if scope == "user":
            if self._user_facts_path is None:
                return  # disabled layer — nothing to do
            self._user_facts_path.parent.mkdir(parents=True, exist_ok=True)
            self._user_facts_path.write_text(
                json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._user_facts_cache = None
            self._user_facts_mtime = None
        else:
            self._facts_path.write_text(
                json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._facts_cache = None
            self._facts_mtime = None
        self._invalidate_context()

    def import_facts(self, facts: list[dict], scope: str = "project") -> int:
        """Merge extracted facts into the store. Returns the number added."""
        added = 0
        for f in facts:
            key = str(f.get("key", "")).strip()
            value = str(f.get("value", "")).strip()
            if not key or not value:
                continue
            tags = [str(t) for t in f.get("tags", []) if str(t).strip()]
            ftype = f.get("type")
            if ftype not in _VALID_TYPES:
                ftype = None
            if self.get_fact(key, scope=scope) != value:
                self.add_fact(key, value, tags, scope=scope, type_=ftype)
                added += 1
        return added


class MemoryExtractor:
    """Auto-extract durable facts from a conversation via the provider.

    `maybe_extract` only re-runs after the conversation grows by
    `growth_threshold` messages since the last extraction. The last extraction
    count persists to `extract_cursor.json` so each session starts where the
    previous one left off (no re-extraction of already-seen history).
    """

    def __init__(self, store: MemoryStore, growth_threshold: int = 20) -> None:
        self._store = store
        self._growth_threshold = growth_threshold
        self._last_count = self._load_cursor()

    def _cursor_path(self) -> Path:
        return self._store.memory_dir / "extract_cursor.json"

    def _load_cursor(self) -> int:
        try:
            data = json.loads(self._cursor_path().read_text(encoding="utf-8"))
            return int(data.get("count", 0))
        except Exception:
            return 0

    def _save_cursor(self) -> None:
        try:
            self._cursor_path().write_text(
                json.dumps({"count": self._last_count}), encoding="utf-8"
            )
        except Exception:
            pass

    def extract(self, provider, messages: list[dict]) -> "int | None":
        """Ask the provider to summarize facts and persist them.

        Facts classified as type "user" route to the global layer; all others
        (including legacy facts without a type) go to the project layer.

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
        project_facts = [f for f in facts if f.get("type") != "user"]
        user_facts = [f for f in facts if f.get("type") == "user"]
        added = self._store.import_facts(project_facts, scope="project")
        if user_facts:
            user_scope = "user" if self._store.user_layer_enabled else "project"
            added += self._store.import_facts(user_facts, scope=user_scope)
        return added

    def maybe_extract(self, provider, messages: list[dict]) -> int:
        if len(messages) - self._last_count < self._growth_threshold:
            return 0
        added = self.extract(provider, messages)
        if added is None:  # extraction failed (e.g. network) — don't advance
            return 0
        self._last_count = len(messages)
        self._save_cursor()
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
