"""Tests for issues found by real-model office scenario testing.

Covers: relative --workdir data-dir nesting, permission-denial prompt
boundary, policy tightening + denied-call accounting, user-approved plan-mode
exit, read-only config queries under PLAN mode, conservative memory extraction,
and the non-interactive one-shot warning.
"""

import argparse
import os
import sys
import threading

from ohwang.modes import Mode
from ohwang.permissions import PermissionManager
from ohwang.providers.base import BaseProvider
from ohwang.services.policy import PolicyLimits
from ohwang.tools import default_tools


class Seq(BaseProvider):
    name = "seq"

    def __init__(self, steps):
        super().__init__("k", "m")
        self.steps = steps
        self.i = 0

    def chat(self, system, messages, tools, max_tokens):
        if self.i < len(self.steps):
            yield from self.steps[self.i]
        self.i += 1


def _results(agent):
    return [
        b
        for m in agent.messages
        for b in (m["content"] if isinstance(m.get("content"), list) else [])
        if b.get("type") == "tool_result"
    ]


# ---------- P0: relative --workdir must not nest .ohwang/ dirs ----------


def test_prepare_workdir_normalizes_to_absolute(tmp_path, monkeypatch):
    from ohwang import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    args = argparse.Namespace(workdir="sub")
    cli._prepare_workdir(args)
    assert args.workdir == str(tmp_path / "sub")
    assert os.getcwd() == str(tmp_path / "sub")


def test_build_agent_workdir_is_absolute_and_unified(tmp_path, monkeypatch):
    from ohwang import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    args = argparse.Namespace(
        provider="deepseek",
        model="",
        api_key="test-key",
        max_tokens=1000,
        auto_approve=True,
        plan=False,
        compact_threshold=10**9,
        base_url=None,
        workdir="sub",
        no_mcp=True,
        no_proactive=True,
    )
    (agent, _renderer, config, _session, _sched, _ext, _skills, _flags) = cli.build_agent(
        args, threading.Lock()
    )
    expected = str(tmp_path / "sub")
    assert config.workdir == expected
    assert not config.workdir.endswith("sub/sub")
    assert str(agent.memory_store.memory_dir) == os.path.join(expected, ".ohwang", "memory")


# ---------- P1a: permission denial is a hard boundary in the prompt ----------


def test_prompt_has_permission_denial_boundary():
    from ohwang.prompts import build_system_prompt

    p = build_system_prompt()
    assert "Permission denied" in p
    assert "HARD BOUNDARY" in p
    assert "retry the denied call" in p
    assert "read source" in p


# ---------- P1b: denied calls count toward the policy budget ----------


def test_permission_denied_counts_toward_policy(tmp_path):
    from tests.helpers import build_agent

    agent, _ = build_agent([], mode=Mode.DEFAULT)
    agent.policy = PolicyLimits(max_tool_calls=1)  # denied call consumes the budget
    steps = [
        [
            {
                "type": "tool_use",
                "id": "x",
                "name": "file_write",
                "input": {"file_path": str(tmp_path / "a.txt"), "content": "b"},
            }
        ],
        [
            {
                "type": "tool_use",
                "id": "y",
                "name": "file_read",
                "input": {"file_path": str(tmp_path / "a.txt")},
            }
        ],
        [{"type": "text", "text": "done"}],
    ]
    agent.provider = Seq(steps)
    agent.run("go")
    results = _results(agent)
    assert len(results) == 2
    assert results[0]["is_error"]
    assert "denied" in results[0]["content"].lower()
    # The denied call already consumed the whole budget, so file_read is capped.
    assert "Policy limit" in results[1]["content"]


# ---------- P1c: exiting plan mode requires user approval ----------


def test_plan_mode_exit_requires_approval():
    # No ask callback -> cannot silently exit read-only plan mode.
    perms = PermissionManager(mode=Mode.PLAN)
    tools = default_tools(permissions=perms)
    assert perms.can_run(tools.get("exit_plan_mode"), {}) is False

    # Callback denies -> still cannot exit.
    perms2 = PermissionManager(mode=Mode.PLAN, ask_callback=lambda n, i: "deny")
    tools2 = default_tools(permissions=perms2)
    assert perms2.can_run(tools2.get("exit_plan_mode"), {}) is False

    # Callback approves -> allowed to exit.
    perms3 = PermissionManager(mode=Mode.PLAN, ask_callback=lambda n, i: "allow")
    tools3 = default_tools(permissions=perms3)
    assert perms3.can_run(tools3.get("exit_plan_mode"), {}) is True


def test_auto_mode_can_still_use_plan_tools():
    perms = PermissionManager(mode=Mode.AUTO)
    tools = default_tools(permissions=perms)
    assert perms.can_run(tools.get("exit_plan_mode"), {}) is True
    assert perms.can_run(tools.get("enter_plan_mode"), {}) is True


# ---------- P1d: read-only config queries work under PLAN mode ----------


def test_plan_mode_allows_config_read_queries():
    perms = PermissionManager(mode=Mode.PLAN)
    tools = default_tools(permissions=perms)
    cfg = tools.get("config")
    assert perms.can_run(cfg, {"action": "list"}) is True
    assert perms.can_run(cfg, {"action": "get", "key": "file_read"}) is True
    # Mutating config actions stay blocked in read-only mode.
    assert perms.can_run(cfg, {"action": "allow", "key": "bash"}) is False
    assert perms.can_run(cfg, {"action": "remove", "key": "bash"}) is False


# ---------- P2: conservative memory extraction ----------


def test_memory_extractor_default_growth_threshold():
    import inspect

    from ohwang.services.memory import MemoryExtractor

    sig = inspect.signature(MemoryExtractor.__init__)
    assert sig.parameters["growth_threshold"].default == 20


def test_memory_extraction_prompt_excludes_ephemeral():
    from ohwang.services import memory

    assert "single session" in memory._MEMORY_EXTRACTION_PROMPT
    assert "meeting recaps" in memory._MEMORY_EXTRACTION_PROMPT


# ---------- P3: non-interactive one-shot warning ----------


def test_warn_noninteractive_approval(monkeypatch, capsys):
    from ohwang import cli

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    args = argparse.Namespace(prompt="do x", auto_approve=False, plan=False)
    cli._warn_noninteractive_approval(args)
    assert "-y" in capsys.readouterr().err

    args2 = argparse.Namespace(prompt="do x", auto_approve=True, plan=False)
    cli._warn_noninteractive_approval(args2)
    assert capsys.readouterr().err == ""

    args3 = argparse.Namespace(prompt="do x", auto_approve=False, plan=True)
    cli._warn_noninteractive_approval(args3)
    assert capsys.readouterr().err == ""

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    args4 = argparse.Namespace(prompt="do x", auto_approve=False, plan=False)
    cli._warn_noninteractive_approval(args4)
    assert capsys.readouterr().err == ""
