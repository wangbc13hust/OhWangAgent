import json

import pytest

from ohwang.services.hooks import HookManager


def test_python_handler_blocks():
    hooks = HookManager()
    hooks.register("pre_tool_use", lambda name, inp: False if name == "bash" else None)
    allowed, _, _ = hooks.run_pre_tool("bash", {"command": "x"})
    assert not allowed
    allowed2, _, _ = hooks.run_pre_tool("file_read", {"file_path": "x"})
    assert allowed2


def test_python_handler_modifies_input():
    hooks = HookManager()
    hooks.register(
        "pre_tool_use",
        lambda name, inp: {"input": {**inp, "command": "echo patched"}},
    )
    allowed, _, new_input = hooks.run_pre_tool("bash", {"command": "rm"})
    assert allowed
    assert new_input["command"] == "echo patched"


def test_python_handler_block_dict():
    hooks = HookManager()
    hooks.register(
        "pre_tool_use",
        lambda name, inp: {"block": True, "reason": "no shell for you"},
    )
    allowed, reason, _ = hooks.run_pre_tool("bash", {"command": "x"})
    assert not allowed
    assert reason == "no shell for you"


def test_post_and_notif_handlers_called():
    hooks = HookManager()
    seen = []
    hooks.register("post_tool_use", lambda name, block: seen.append(("post", name)))
    hooks.register("notif", lambda msg: seen.append(("notif", msg)))
    hooks.run_post_tool("bash", {"type": "tool_result"})
    hooks.notify("hello")
    assert ("post", "bash") in seen
    assert ("notif", "hello") in seen


def test_post_and_notif_swallow_handler_errors():
    hooks = HookManager()

    def _boom(name, block):
        raise RuntimeError("boom")

    def _boom2(msg):
        raise RuntimeError("boom2")

    hooks.register("post_tool_use", _boom)
    hooks.register("notif", _boom2)
    hooks.run_post_tool("bash", {})  # must not raise
    hooks.notify("x")  # must not raise


def test_load_json_and_cmd_block(tmp_path):
    d = tmp_path / ".ohwang"
    d.mkdir()
    (d / "hooks.json").write_text(
        json.dumps(
            {
                "pre_tool_use": [{"tool": "bash", "command": "exit 1"}],
                "notif": [{"command": "echo hi"}],
            }
        ),
        encoding="utf-8",
    )
    hooks = HookManager(str(tmp_path))
    assert hooks.load_json() == 2
    allowed, reason, _ = hooks.run_pre_tool("bash", {"command": "x"})
    assert not allowed
    assert "blocked" in reason
    allowed2, _, _ = hooks.run_pre_tool("file_read", {"file_path": "x"})
    assert allowed2


def test_cmd_tool_glob_filter(tmp_path):
    d = tmp_path / ".ohwang"
    d.mkdir()
    (d / "hooks.json").write_text(
        json.dumps({"pre_tool_use": [{"tool": "bash*", "command": "exit 1"}]}),
        encoding="utf-8",
    )
    hooks = HookManager(str(tmp_path))
    hooks.load_json()
    assert not hooks.run_pre_tool("bash", {})[0]
    assert not hooks.run_pre_tool("bash_pw", {})[0]
    assert hooks.run_pre_tool("grep", {})[0]


def test_cmd_post_and_notif_do_not_block(tmp_path):
    d = tmp_path / ".ohwang"
    d.mkdir()
    (d / "hooks.json").write_text(
        json.dumps(
            {
                "post_tool_use": [{"tool": "bash", "command": "exit 1"}],
                "notif": [{"command": "exit 1"}],
            }
        ),
        encoding="utf-8",
    )
    hooks = HookManager(str(tmp_path))
    hooks.load_json()
    hooks.run_post_tool("bash", {})  # must not raise
    hooks.notify("hi")  # must not raise


def test_load_json_bad_file(tmp_path):
    hooks = HookManager(str(tmp_path))
    (tmp_path / ".ohwang").mkdir(exist_ok=True)
    (tmp_path / ".ohwang" / "hooks.json").write_text("{bad", encoding="utf-8")
    assert hooks.load_json() == 0


def test_load_json_without_workdir():
    hooks = HookManager()
    assert hooks.load_json() == 0


def test_unknown_event_rejected():
    hooks = HookManager()
    with pytest.raises(ValueError):
        hooks.register("bogus", lambda: None)


def test_cmd_runs_in_workdir(tmp_path):
    (tmp_path / ".ohwang").mkdir()
    (tmp_path / ".ohwang" / "hooks.json").write_text(
        json.dumps(
            {
                "notif": [{"command": "powershell -NoProfile -Command \"Set-Content -Path probe.txt -Value 'cwd-ok'\""}]
            }
        ),
        encoding="utf-8",
    )
    hooks = HookManager(str(tmp_path))
    hooks.load_json()
    hooks.notify("go")
    assert (tmp_path / "probe.txt").exists()
    assert (tmp_path / "probe.txt").read_text(encoding="utf-8").strip() == "cwd-ok"


def test_load_json_accepts_bom(tmp_path):
    d = tmp_path / ".ohwang"
    d.mkdir()
    (d / "hooks.json").write_bytes(
        b"\xef\xbb\xbf" + json.dumps(
            {"post_tool_use": [{"command": "echo hi"}]}
        ).encode("utf-8")
    )
    hooks = HookManager(str(tmp_path))
    assert hooks.load_json() == 1


def test_emit_new_events_called_with_kwargs():
    hooks = HookManager()
    seen = []
    hooks.register("user_prompt_submit", lambda **kw: seen.append(kw))
    hooks.register("stop", lambda **kw: seen.append(("stop", kw)))
    hooks.emit("user_prompt_submit", prompt="hi")
    hooks.emit("stop", final_text="done")
    assert seen[0] == {"prompt": "hi"}
    assert seen[1] == ("stop", {"final_text": "done"})


def test_emit_unknown_event_rejected():
    hooks = HookManager()
    with pytest.raises(ValueError):
        hooks.emit("no_such_event")


def test_emit_swallows_handler_errors():
    hooks = HookManager()

    def boom(**kw):
        raise RuntimeError("handler crash")

    hooks.register("session_start", boom)
    hooks.emit("session_start")  # must not raise


def test_agent_run_fires_prompt_and_stop():
    from ohwang.agent import Agent
    from ohwang.config import Config
    from ohwang.modes import Mode
    from ohwang.permissions import PermissionManager
    from ohwang.prompts import build_system_prompt
    from ohwang.tools import default_tools
    from ohwang.tools.todo import TodoStore
    from tests.helpers import ScriptedProvider

    events = []
    hooks = HookManager()
    hooks.register("user_prompt_submit", lambda **kw: events.append(("submit", kw)))
    hooks.register("stop", lambda **kw: events.append(("stop", kw)))

    config = Config(workdir=".", auto_approve=True).resolve()
    provider = ScriptedProvider([[{"type": "text", "text": "hello back"}]])
    perms = PermissionManager(mode=Mode.AUTO)
    tools = default_tools(
        todo_store=TodoStore(), permissions=perms, search_provider=None
    )
    agent = Agent(
        provider,
        tools,
        perms,
        config,
        build_system_prompt(config.workdir),
        hooks=hooks,
    )
    out = agent.run("hello")
    assert out == "hello back"
    submits = [e for e in events if e[0] == "submit"]
    stops = [e for e in events if e[0] == "stop"]
    assert submits and submits[0][1]["prompt"] == "hello"
    assert stops and "hello back" in stops[0][1]["final_text"]


def test_agent_tool_emits_subagent_hooks():
    from ohwang.tools.agent_tool import AgentTool

    events = []
    hooks = HookManager()
    hooks.register("subagent_start", lambda **kw: events.append(("start", kw)))
    hooks.register("subagent_stop", lambda **kw: events.append(("stop", kw)))

    class _R:
        def run(self, prompt, **kwargs):
            return "done"

    tool = AgentTool(lambda: _R(), hooks=hooks)
    r = tool.execute({"description": "d", "prompt": "p"})
    assert r.is_error is False
    starts = [e for e in events if e[0] == "start"]
    stops = [e for e in events if e[0] == "stop"]
    assert starts and starts[0][1]["prompt"] == "p"
    assert starts[0][1]["description"] == "d"
    assert stops
