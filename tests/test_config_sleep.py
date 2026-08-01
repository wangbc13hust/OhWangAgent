import json

from ohwang.tools.config import ConfigTool
from ohwang.tools.sleep import SleepTool


def test_config_list_empty(tmp_path):
    r = ConfigTool(str(tmp_path)).execute({"action": "list"})
    assert not r.is_error
    assert "allow: (none)" in r.content
    assert "deny: (none)" in r.content


def test_config_add_and_persist(tmp_path):
    tool = ConfigTool(str(tmp_path))
    r = tool.execute({"action": "allow", "key": "file_read"})
    assert not r.is_error
    data = json.loads((tmp_path / ".ohwang" / "settings.json").read_text(encoding="utf-8"))
    assert data["permissions"]["allow"] == ["file_read"]
    assert "file_read" in tool.execute({"action": "list"}).content


def test_config_get_rules(tmp_path):
    tool = ConfigTool(str(tmp_path))
    tool.execute({"action": "allow", "key": "bash"})
    tool.execute({"action": "deny", "key": "file_write"})
    assert "bash is allow" in tool.execute({"action": "get", "key": "bash"}).content
    assert "file_write is deny" in tool.execute({"action": "get", "key": "file_write"}).content
    assert "no rule" in tool.execute({"action": "get", "key": "grep"}).content


def test_config_get_section(tmp_path):
    tool = ConfigTool(str(tmp_path))
    tool.execute({"action": "allow", "key": "bash"})
    r = tool.execute({"action": "get", "key": "allow"})
    assert "bash" in r.content


def test_config_remove(tmp_path):
    tool = ConfigTool(str(tmp_path))
    tool.execute({"action": "allow", "key": "bash"})
    r = tool.execute({"action": "remove", "key": "bash"})
    assert not r.is_error
    assert "no rule" in tool.execute({"action": "get", "key": "bash"}).content


def test_config_requires_key_for_section(tmp_path):
    r = ConfigTool(str(tmp_path)).execute({"action": "allow"})
    assert r.is_error
    assert "requires 'key'" in r.content


def test_config_updates_live_permissions(tmp_path):
    from ohwang.modes import Mode
    from ohwang.permissions import PermissionManager

    perms = PermissionManager(mode=Mode.DEFAULT)
    tool = ConfigTool(str(tmp_path), permissions=perms)
    tool.execute({"action": "allow", "key": "bash"})
    from ohwang.tools.bash import BashTool

    assert perms.can_run(BashTool(), {"command": "echo hi"}) is True


def test_sleep_returns():
    r = SleepTool().execute({"seconds": 1})
    assert not r.is_error
    assert "Slept 1s" in r.content


def test_sleep_clamp():
    assert SleepTool._clamp(999999) == 3600
    assert SleepTool._clamp(-5) == 1
    assert SleepTool._clamp(10) == 10
