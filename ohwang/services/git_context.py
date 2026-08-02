"""Compact git repository snapshot for the system prompt.

Injects the current branch, recent commits, and working-tree status so the
agent knows what code it is operating on (mirror of Claude Code's repository
context). Any failure — not a repo, git missing, timeout, encoding issues —
yields "" so the system-prompt build never crashes on git.

Refreshed at most once per _TTL_SECONDS per workdir: the system-prompt cache
already limits builds to one per turn, but many turns (and many tests) share
the same repo, and spawning two git subprocesses every build would be wasteful.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

_TTL_SECONDS = 5.0

_cache: dict[Path, tuple[float, str]] = {}


def git_context(workdir: str | Path | None) -> str:
    """Return a compact git context block for `workdir`, or "" if unavailable."""
    if not workdir:
        return ""
    wd = Path(workdir)
    now = time.monotonic()
    entry = _cache.get(wd)
    if entry is not None and now - entry[0] < _TTL_SECONDS:
        return entry[1]
    ctx = _compute(wd)
    _cache[wd] = (now, ctx)
    return ctx


def _compute(workdir: Path) -> str:
    try:
        status = _git(workdir, "status", "--short", "--branch")
        log = _git(workdir, "log", "--oneline", "-5")
    except Exception:
        return ""

    branch = ""
    status_lines: list[str] = []
    for line in status.splitlines():
        if line.startswith("## "):
            # "## main...origin/main" -> "main"
            branch = line[3:].split("...")[0].strip()
        elif line:
            status_lines.append(line)
    if not branch:
        return ""

    lines = ["# Git Context", f"Branch: {branch}"]
    if log.strip():
        lines.append("Recent commits:")
        lines.extend(f"  {l}" for l in log.splitlines() if l)
    if status_lines:
        lines.append("Working tree:")
        lines.extend(f"  {l}" for l in status_lines)
    return "\n".join(lines)


def _git(workdir: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(workdir), *args],
        capture_output=True,
        text=True,
        timeout=10,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} exited {proc.returncode}")
    return proc.stdout
