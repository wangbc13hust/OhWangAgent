from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


_DEFAULTS = {
    "web_fetch": True,
    "web_search": True,
    "web_browser": False,
    "ask_user": True,
    "agent_tool": True,
    "mcp": True,
    "lsp": False,
    "skill": True,
    "plugin": False,
    "memory": True,
    "todo": True,
    "plan_mode": True,
    "compact": True,
    "session": True,
    "coordinator": False,
    "agent_swarms": False,
    "worktree": False,
    "workflow_scripts": False,
    "tool_search": False,
    "proactive": False,
}


class FeatureFlags:
    """Feature flag system driven by environment variables + .ohwang/flags.json.

    Priority (highest wins):
      1. Environment variable: OHWANG_FEATURE_<NAME>=1|0
      2. .ohwang/flags.json: {"features": {"<name>": true|false}}
      3. Built-in defaults
    """

    def __init__(self, workdir: str | Path) -> None:
        self.workdir = Path(workdir)
        self._overrides: dict[str, bool] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = self.workdir / ".ohwang" / "flags.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.get("features", {}).items():
                    if isinstance(v, bool):
                        self._overrides[k] = v
            except Exception:
                pass

    def is_enabled(self, name: str) -> bool:
        env_key = f"OHWANG_FEATURE_{name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val in ("1", "true", "yes")

        self._ensure_loaded()
        if name in self._overrides:
            return self._overrides[name]

        return _DEFAULTS.get(name, False)

    def enable(self, name: str) -> None:
        self._ensure_loaded()
        self._overrides[name] = True
        self._save()

    def disable(self, name: str) -> None:
        self._ensure_loaded()
        self._overrides[name] = False
        self._save()

    def list_all(self) -> dict[str, bool]:
        self._ensure_loaded()
        result = dict(_DEFAULTS)
        result.update(self._overrides)
        for name in list(result):
            env_key = f"OHWANG_FEATURE_{name.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                result[name] = env_val in ("1", "true", "yes")
        return result

    def _save(self) -> None:
        path = self.workdir / ".ohwang" / "flags.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"features": self._overrides}
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
