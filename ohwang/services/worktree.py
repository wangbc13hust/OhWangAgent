from __future__ import annotations

import json
import subprocess
from pathlib import Path


class WorktreeManager:
    """Manage git worktrees for isolated, parallel development contexts.

    The manager records the active (self-created) worktree in
    `.ohwang/worktree.json` so it can be removed on exit.
    """

    def __init__(self, workdir: str | Path) -> None:
        self.workdir = Path(workdir)
        self._state_file = self.workdir / ".ohwang" / "worktree.json"

    def _git(self, *args: str) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.workdir), *args],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return 1, "", "git command timed out"
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    def is_git_repo(self) -> bool:
        code, _, _ = self._git("rev-parse", "--is-inside-work-tree")
        return code == 0

    def add(self, branch: str, path: str | None = None) -> tuple[bool, str]:
        if not self.is_git_repo():
            return False, "Not inside a git repository."
        target = str(path) if path else str(self.workdir.parent / f"{branch}")
        code, out, err = self._git("worktree", "add", "-b", branch, target)
        if code != 0:
            return False, (out + err).strip() or "git worktree add failed"
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps({"branch": branch, "path": target}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True, f"Created worktree at {target} on branch {branch}."

    def remove(self) -> tuple[bool, str]:
        if not self._state_file.is_file():
            return False, "No active worktree tracked in this session."
        state = json.loads(self._state_file.read_text(encoding="utf-8"))
        code, out, err = self._git("worktree", "remove", "--force", state["path"])
        if code != 0:
            return False, (out + err).strip() or "git worktree remove failed"
        self._state_file.unlink(missing_ok=True)
        return True, f"Removed worktree {state['path']} (branch {state['branch']})."

    def list(self) -> str:
        code, out, err = self._git("worktree", "list")
        if code != 0:
            return (out + err).strip() or "git worktree list failed"
        return out.strip()
