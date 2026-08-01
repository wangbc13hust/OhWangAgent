from __future__ import annotations

import json
import os
import time
from pathlib import Path


class SessionStore:
    """Persists conversation history to .ohwang/sessions/*.json."""

    def __init__(self, base_dir: str | Path) -> None:
        self.dir = Path(base_dir) / ".ohwang" / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict]:
        items: list[dict] = []
        for f in sorted(self.dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            items.append(
                {
                    "id": f.stem,
                    "mtime": data.get("mtime", 0),
                    "preview": data.get("preview", ""),
                    "summary": data.get("summary", ""),
                    "n_messages": len(data.get("messages", [])),
                }
            )
        return items

    def save(self, messages: list[dict], preview: str = "", summary: str = "") -> str:
        base = time.strftime("%Y%m%d-%H%M%S")
        sid = base
        n = 0
        while (self.dir / f"{sid}.json").exists():
            n += 1
            sid = f"{base}-{n}"
        path = self.dir / f"{sid}.json"
        data = {
            "mtime": time.time(),
            "preview": preview,
            "summary": summary,
            "messages": messages,
        }
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return sid

    def load(self, sid: str) -> list[dict] | None:
        data = self.load_full(sid)
        return data.get("messages") if data is not None else None

    def load_full(self, sid: str) -> dict | None:
        """Return the whole saved session dict (messages, summary, preview)."""
        path = self.dir / f"{sid}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None
        return data
