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
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"allow": [], "ask": [], "deny": []}
    perms = data.get("permissions", {})
    return {
        "allow": list(perms.get("allow", [])),
        "ask": list(perms.get("ask", [])),
        "deny": list(perms.get("deny", [])),
    }


def save_settings(workdir: str | Path, settings: dict) -> None:
    """Persist permission rules to .ohwang/settings.json."""
    path = Path(workdir) / ".ohwang" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "permissions": {
            "allow": list(settings.get("allow", [])),
            "ask": list(settings.get("ask", [])),
            "deny": list(settings.get("deny", [])),
        }
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_settings(workdir: str | Path, action: str, key: str, value: str) -> dict:
    """Add ('allow'|'ask'|'deny') or remove ('remove') a rule, persisted + returned."""
    settings = load_settings(workdir)
    sections = ("allow", "ask", "deny")
    if action in sections:
        if key not in settings[action]:
            settings[action].append(key)
        save_settings(workdir, settings)
        return settings
    if action == "remove":
        for section in sections:
            settings[section] = [r for r in settings[section] if r != key]
        save_settings(workdir, settings)
        return settings
    raise ValueError(f"unknown action: {action}")
