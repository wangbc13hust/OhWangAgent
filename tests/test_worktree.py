import os
import subprocess
import tempfile

from ohwang.services.worktree import WorktreeManager
from ohwang.tools.worktree import EnterWorktreeTool, ExitWorktreeTool


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def _make_repo():
    d = tempfile.mkdtemp()
    _git(d, "init")
    _git(d, "config", "user.email", "test@test")
    _git(d, "config", "user.name", "test")
    with open(os.path.join(d, "a.txt"), "w") as f:
        f.write("hi")
    _git(d, "add", ".")
    _git(d, "commit", "-m", "init")
    return d


def test_add_list_remove_worktree():
    d = _make_repo()
    mgr = WorktreeManager(d)
    wt_path = os.path.join(d, "wt")
    ok, msg = mgr.add("feature-x", path=wt_path)
    assert ok, msg
    listing = mgr.list()
    assert wt_path.replace("\\", "/") in listing
    ok2, _ = mgr.remove()
    assert ok2
    assert wt_path.replace("\\", "/") not in mgr.list()


def test_add_fails_outside_git_repo():
    d = tempfile.mkdtemp()
    mgr = WorktreeManager(d)
    ok, msg = mgr.add("feature-y", path=os.path.join(d, "wt"))
    assert not ok
    assert "git repository" in msg.lower()


def test_remove_without_state():
    d = _make_repo()
    mgr = WorktreeManager(d)
    ok, msg = mgr.remove()
    assert not ok
    assert "No active worktree" in msg


def test_enter_exit_tools_roundtrip():
    d = _make_repo()
    mgr = WorktreeManager(d)
    enter = EnterWorktreeTool(mgr)
    exit_ = ExitWorktreeTool(mgr)
    wt_path = os.path.join(d, "wt2")
    r = enter.execute({"branch": "feature-z", "path": wt_path})
    assert not r.is_error
    assert "Created worktree" in r.content
    r2 = exit_.execute({})
    assert not r2.is_error
    assert "Removed worktree" in r2.content
