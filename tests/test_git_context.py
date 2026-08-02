"""Git context injection tests."""

from __future__ import annotations

import subprocess

from ohwang.services.git_context import git_context


def _git(wd, *args):
    subprocess.run(
        ["git", "-C", str(wd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "a.txt").write_text("hi\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial commit")
    return path


def test_non_repo_returns_empty(tmp_path):
    assert git_context(tmp_path) == ""


def test_repo_returns_branch_and_commits(tmp_path):
    repo = _init_repo(tmp_path / "r")
    ctx = git_context(repo)
    assert "Git Context" in ctx
    assert "Branch:" in ctx
    assert "initial commit" in ctx


def test_repo_includes_working_tree_changes(tmp_path):
    repo = _init_repo(tmp_path / "r")
    (repo / "b.txt").write_text("new\n", encoding="utf-8")
    ctx = git_context(repo)
    assert "Working tree:" in ctx
    assert "b.txt" in ctx


def test_effective_system_injects_git_context(tmp_path):
    from ohwang.agent import Agent
    from ohwang.config import Config
    from ohwang.modes import Mode
    from ohwang.permissions import PermissionManager
    from ohwang.tools.registry import ToolRegistry

    repo = _init_repo(tmp_path / "r")
    agent = Agent(
        provider=None,
        tools=ToolRegistry(),
        permissions=PermissionManager(mode=Mode.AUTO),
        config=Config(workdir=str(repo)).resolve(),
        system="SYSTEM_BASE",
    )
    system = agent._effective_system()
    assert "SYSTEM_BASE" in system
    assert "Git Context" in system
    assert "Branch:" in system
