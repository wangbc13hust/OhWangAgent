import json

from ohwang.services.policy import PolicyLimits
from ohwang.services.summary import UsageTracker


def test_policy_total_cap():
    p = PolicyLimits(max_tool_calls=2)
    assert p.check_tool("bash")
    p.record("bash")
    assert p.check_tool("bash")
    p.record("bash")
    assert not p.check_tool("bash")


def test_policy_per_tool_cap():
    p = PolicyLimits(per_tool={"bash": 1})
    assert p.check_tool("bash")
    p.record("bash")
    assert not p.check_tool("bash")
    assert p.check_tool("file_read")


def test_policy_load_from_file(tmp_path):
    d = tmp_path / ".ohwang"
    d.mkdir()
    (d / "policy.json").write_text(
        json.dumps({"max_tool_calls": 5, "per_tool": {"web_search": 2}}),
        encoding="utf-8",
    )
    p = PolicyLimits.load(str(tmp_path))
    assert p.max_tool_calls == 5
    assert p.limit_for("web_search") == 2


def test_policy_load_missing_defaults(tmp_path):
    p = PolicyLimits.load(str(tmp_path))
    assert p.max_tool_calls == 200
    assert p.limit_for("bash") is None


def test_usage_records_and_reports():
    u = UsageTracker()
    u.record("bash", False)
    u.record("bash", True)
    u.record("file_read", False)
    report = u.report()
    assert "Tool calls: 3" in report
    assert "bash: 2" in report
    assert "1 errors" in report


def test_usage_empty_report():
    assert "No tool calls" in UsageTracker().report()


def test_usage_helpers():
    u = UsageTracker()
    u.record("grep", True)
    assert u.calls_for("grep") == 1
    assert u.errors_for("grep") == 1
    assert u.calls_for("bash") == 0
    assert u.errors_for("bash") == 0
