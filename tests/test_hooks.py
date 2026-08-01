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
