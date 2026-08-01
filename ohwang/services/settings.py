from __future__ import annotations

import json
from pathlib import Path


def load_settings(workdir: str | Path) -> dict:
    """Load permission rules from .ohwang/settings.json.

    Schema:
      { "permissions": { "allow": [...], "ask": [...], "deny": [...] } }
    Entries are tool names or glob patterns (e.g. "mcp__*").
    """
    path = Path(workdir) / ".ohwang" / "settings.json"
    if not path.is_file():
        return {"allow": [], "ask": [], "deny": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"allow": [], "ask": [], "deny": []}
    perms = data.get("permissions", {})
    return {
        "allow": list(perms.get("allow", [])),
        "ask": list(perms.get("ask", [])),
        "deny": list(perms.get("deny", [])),
    }
