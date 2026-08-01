from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class PolicyLimits:
    """Enforce per-tool and total tool-call caps to stop runaway loops.

    Loads from `.ohwang/policy.json`:
      { "max_tool_calls": 1000, "per_tool": {"bash": 100, "web_search": 50} }
    """

    def __init__(
        self,
        max_tool_calls: int = 200,
        per_tool: Optional[dict[str, int]] = None,
    ) -> None:
        self.max_tool_calls = max_tool_calls
        self.per_tool = dict(per_tool or {})
        self._counts: dict[str, int] = {}
        self.total = 0

    @classmethod
    def load(cls, workdir: str | Path) -> "PolicyLimits":
        path = Path(workdir) / ".ohwang" / "policy.json"
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return cls()
        return cls(
            max_tool_calls=int(data.get("max_tool_calls", 1000)),
            per_tool={k: int(v) for k, v in data.get("per_tool", {}).items()},
        )

    def check_tool(self, name: str) -> bool:
        if self.total >= self.max_tool_calls:
            return False
        limit = self.per_tool.get(name)
        if limit is not None and self._counts.get(name, 0) >= limit:
            return False
        return True

    def record(self, name: str) -> None:
        self._counts[name] = self._counts.get(name, 0) + 1
        self.total += 1

    def limit_for(self, name: str) -> Optional[int]:
        return self.per_tool.get(name)
