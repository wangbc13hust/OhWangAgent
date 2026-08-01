from __future__ import annotations

from collections import Counter


class UsageTracker:
    """Tracks tool-call usage and errors for session summaries.

    Mirrors Claude Code's toolUseSummary / AgentSummary.
    """

    def __init__(self) -> None:
        self._calls: Counter = Counter()
        self._errors: Counter = Counter()
        self.total = 0

    def record(self, name: str, is_error: bool) -> None:
        self._calls[name] += 1
        self.total += 1
        if is_error:
            self._errors[name] += 1

    def calls_for(self, name: str) -> int:
        return self._calls.get(name, 0)

    def errors_for(self, name: str) -> int:
        return self._errors.get(name, 0)

    def report(self) -> str:
        if self.total == 0:
            return "No tool calls recorded."
        lines = [f"Tool calls: {self.total}"]
        for name, n in self._calls.most_common():
            err = self._errors.get(name, 0)
            suffix = f"  ({err} errors)" if err else ""
            lines.append(f"  {name}: {n}{suffix}")
        return "\n".join(lines)
