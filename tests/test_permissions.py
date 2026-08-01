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
