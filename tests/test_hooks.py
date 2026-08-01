import json

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


def test_post_and_notif_handlers_called():
    hooks = HookManager()
    seen = []
    hooks.register("post_tool_use", lambda name, block: seen.append(("post", name)))
    hooks.register("notif", lambda msg: seen.append(("notif", msg)))
    hooks.run_post_tool("bash", {"type": "tool_result"})
    hooks.notify("hello")
    assert ("post", "bash") in seen
    assert ("notif", "hello") in seen


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


def test_unknown_event_rejected():
    hooks = HookManager()
    try:
        hooks.register("bogus", lambda: None)
        assert False, "should have raised"
    except ValueError:
        pass
