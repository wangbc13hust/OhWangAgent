from ohwang.modes import Mode
from ohwang.permissions import PermissionManager


class _Tool:
    def __init__(self, name, default_permission="ask"):
        self.name = name
        self.default_permission = default_permission


def test_rules_override_default():
    perms = PermissionManager(mode=Mode.DEFAULT, rules={"bash": "allow"})
    assert perms.can_run(_Tool("bash"), {"command": "x"}) is True


def test_always_allow_remembered():
    calls = []

    def ask(name, inp):
        calls.append(name)
        return "always"

    perms = PermissionManager(mode=Mode.DEFAULT, ask_callback=ask)
    t = _Tool("bash")
    assert perms.can_run(t, {"command": "echo"}) is True
    assert perms.can_run(t, {"command": "echo"}) is True
    assert len(calls) == 1


def test_ask_deny():
    perms = PermissionManager(mode=Mode.DEFAULT, ask_callback=lambda n, i: "deny")
    assert perms.can_run(_Tool("bash"), {"command": "x"}) is False


def test_auto_approve_property_flips_mode():
    perms = PermissionManager(mode=Mode.DEFAULT)
    assert perms.auto_approve is False
    perms.auto_approve = True
    assert perms.mode is Mode.AUTO
    perms.auto_approve = False
    assert perms.mode is Mode.DEFAULT


def test_allow_list_overrides_default():
    perms = PermissionManager(mode=Mode.DEFAULT, allow=["bash"])
    assert perms.can_run(_Tool("bash"), {"command": "rm -rf /"}) is True


def test_deny_list_blocks_even_with_allow():
    perms = PermissionManager(mode=Mode.DEFAULT, allow=["bash"], deny=["bash"])
    assert perms.can_run(_Tool("bash"), {"command": "x"}) is False


def test_ask_list_triggers_callback():
    calls = []
    perms = PermissionManager(
        mode=Mode.DEFAULT,
        ask=["bash"],
        ask_callback=lambda n, i: calls.append(n) or "allow",
    )
    assert perms.can_run(_Tool("bash"), {"command": "x"}) is True
    assert calls == ["bash"]


def test_glob_patterns_match_tool_names():
    perms = PermissionManager(mode=Mode.DEFAULT, allow=["mcp__*"])
    assert perms.can_run(_Tool("mcp__files__read"), {"path": "x"}) is True
    assert perms.can_run(_Tool("bash"), {"command": "x"}) is False


def test_rules_priority_after_patterns():
    perms = PermissionManager(mode=Mode.DEFAULT, deny=["*"], rules={"bash": "allow"})
    assert perms.can_run(_Tool("bash"), {"command": "x"}) is False
