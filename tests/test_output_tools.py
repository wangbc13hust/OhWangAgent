import os

from ohwang.services.summary import UsageTracker
from ohwang.tools.brief import BriefTool
from ohwang.tools.snip import SnipTool
from ohwang.tools.synthetic_output import SyntheticOutputTool
from ohwang.tools.todo import TodoStore


def test_synthetic_output_shows_text():
    shown = []
    r = SyntheticOutputTool(display=shown.append).execute({"text": "hello user"})
    assert shown == ["hello user"]
    assert r.content == "(shown to user)"
    assert not r.is_error


def test_synthetic_output_default_permission_allow():
    assert SyntheticOutputTool().default_permission == "allow"


def test_synthetic_output_no_callback_safe():
    r = SyntheticOutputTool().execute({"text": "x"})
    assert not r.is_error


def test_brief_reports_counts():
    usage = UsageTracker()
    usage.record("file_read", False)
    usage.record("bash", True)
    todo = TodoStore()
    todo.set(
        [
            {"content": "a", "status": "completed", "priority": "high"},
            {"content": "b", "status": "pending", "priority": "medium"},
        ]
    )
    r = BriefTool(usage, todo, lambda: 7).execute({"focus": "report"})
    assert not r.is_error
    assert "Focus: report" in r.content
    assert "Iterations: 7" in r.content
    assert "Tool calls: 2" in r.content
    assert "Tool errors: 1" in r.content
    assert "Todos: 1 done, 1 pending" in r.content


def test_brief_without_deps():
    r = BriefTool().execute({})
    assert not r.is_error
    assert "Iterations: ?" in r.content


def test_snip_saves_file(tmp_path):
    r = SnipTool(str(tmp_path)).execute({"text": "some output line", "title": "build log"})
    assert not r.is_error
    saved = list((tmp_path / ".ohwang" / "snips").glob("build log-*.txt"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == "some output line"
    assert str(saved[0]) in r.content


def test_snip_sanitizes_title(tmp_path):
    r = SnipTool(str(tmp_path)).execute({"text": "x", "title": "a/b:c*d"})
    assert not r.is_error
    assert "a_b_c_d" in r.content


def test_tools_registered_in_default_registry():
    from ohwang.tools import default_tools

    usage = UsageTracker()
    t = default_tools(workdir=os.getcwd(), usage=usage, iterations_getter=lambda: 0)
    for name in ("synthetic_output", "brief", "snip"):
        assert name in t
