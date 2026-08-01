import json
import os
import sys
import tempfile

from ohwang.modes import Mode
from ohwang.services.session import SessionStore
from ohwang.services.tokens import estimate_messages_tokens
from ohwang.services.worktree import WorktreeManager
from ohwang.tools.file_edit import FileEditTool
from ohwang.tools.glob import GlobTool
from ohwang.tools.grep import GrepTool
from ohwang.tools.memory import MemoryReadTool, MemoryWriteTool
from ohwang.tools.registry import ToolRegistry


# ---------- modes ----------

def test_mode_label():
    assert Mode.DEFAULT.label == "DEFAULT"
    assert Mode.PLAN.label == "PLAN"
    assert Mode.AUTO.label == "AUTO"
    assert Mode.BYPASS.label == "BYPASS"


# ---------- session: corrupted file skipped ----------

def test_session_list_skips_corrupt(tmp_path):
    s = SessionStore(str(tmp_path))
    s.save([{"role": "user", "content": [{"type": "text", "text": "a"}]}], preview="ok")
    bad = tmp_path / ".ohwang" / "sessions" / "bad.json"
    bad.write_text("{corrupt", encoding="utf-8")
    items = s.list()
    assert len(items) == 1


def test_session_load_corrupt_returns_none(tmp_path):
    s = SessionStore(str(tmp_path))
    bad = tmp_path / ".ohwang" / "sessions" / "bad.json"
    bad.write_text("{corrupt", encoding="utf-8")
    assert s.load("bad") is None


def test_session_list_sorts_by_mtime(tmp_path):
    s = SessionStore(str(tmp_path))
    s.save([{"role": "user", "content": [{"type": "text", "text": "a"}]}], preview="first")
    s.save([{"role": "user", "content": [{"type": "text", "text": "b"}]}], preview="second")
    items = s.list()
    assert items[0]["preview"] == "second"


# ---------- tokens: string content and non-list skip ----------

def test_tokens_plain_string_message():
    msgs = [{"role": "user", "content": "hello world"}]
    assert estimate_messages_tokens(msgs) > 0


def test_tokens_skips_unknown_content():
    msgs = [{"role": "user", "content": 42}]
    total = estimate_messages_tokens(msgs)
    assert total == 4  # only per-message overhead


# ---------- file_edit: read/write OSError branches ----------

def test_file_edit_cannot_read(monkeypatch, tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("abc", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("perm denied")

    monkeypatch.setattr("builtins.open", boom)
    r = FileEditTool().execute({"file_path": str(p), "old_string": "a", "new_string": "b"})
    assert r.is_error
    assert "Cannot read file" in r.content


def test_file_edit_cannot_write(monkeypatch, tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("abc", encoding="utf-8")
    real_open = open
    calls = {"n": 0}

    def flaky_open(*a, **k):
        calls["n"] += 1
        if calls["n"] >= 2:  # second call is the write
            raise OSError("readonly")
        return real_open(*a, **k)

    monkeypatch.setattr("builtins.open", flaky_open)
    r = FileEditTool().execute({"file_path": str(p), "old_string": "a", "new_string": "b"})
    assert r.is_error
    assert "Cannot write file" in r.content


# ---------- glob: prefix non-dir, non-recursive ----------

def test_glob_prefix_not_dir(tmp_path):
    (tmp_path / "f.txt").write_text("", encoding="utf-8")
    r = GlobTool().execute({"pattern": "f.txt/**/*.py", "path": str(tmp_path)})
    assert "No files matched" in r.content


def test_glob_non_recursive(tmp_path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("", encoding="utf-8")
    r = GlobTool().execute({"pattern": "*.py", "path": str(tmp_path)})
    assert "a.py" in r.content
    assert "b.py" not in r.content


# ---------- grep: max_matches stop, unreadable file, non-dir path ----------

def test_grep_stops_at_max(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("match\n" * 300, encoding="utf-8")
    r = GrepTool().execute({"pattern": "match", "path": str(f)})
    assert "stopped at 200 matches" in r.content


def test_grep_skips_unreadable_file(monkeypatch, tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("match\n", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr("builtins.open", boom)
    r = GrepTool().execute({"pattern": "match", "path": str(p)})
    assert "No matches found" in r.content


# ---------- memory tools ----------

class _FakeStore:
    def __init__(self):
        self.facts = {}

    def search_facts(self, q):
        return [{"key": "k", "value": "v", "tags": []}]

    def load_project_context(self):
        return "PROJECT_CTX"

    def render_context(self):
        return "RENDERED"

    def add_fact(self, key, value, tags):
        self.facts[key] = (value, tags)


def test_memory_read_query_hits():
    r = MemoryReadTool(_FakeStore()).execute({"query": "x"})
    assert not r.is_error
    assert "**k**" in r.content


def test_memory_read_no_query():
    r = MemoryReadTool(_FakeStore()).execute({})
    assert r.content == "RENDERED"


def test_memory_write_saves_fact():
    store = _FakeStore()
    r = MemoryWriteTool(store).execute({"key": "k1", "value": "v1", "tags": ["a"]})
    assert not r.is_error
    assert "Saved fact: k1" in r.content
    assert store.facts["k1"] == ("v1", ["a"])


class _NoMatchStore(_FakeStore):
    def search_facts(self, q):
        return []


def test_memory_read_query_no_match_with_context():
    r = MemoryReadTool(_NoMatchStore()).execute({"query": "zzz"})
    assert "PROJECT_CTX" in r.content


def test_memory_read_query_no_match_no_context():
    class Empty:
        def search_facts(self, q):
            return []

        def load_project_context(self):
            return ""

    r = MemoryReadTool(Empty()).execute({"query": "zzz"})
    assert "No matching facts" in r.content


# ---------- worktree: git failure paths ----------

def test_worktree_add_git_error(tmp_path):
    mgr = WorktreeManager(str(tmp_path))
    mgr._git = lambda *a, **k: (1, "", "repo broken")
    mgr.is_git_repo = lambda: True
    ok, msg = mgr.add("branch-x", path=str(tmp_path / "wt"))
    assert not ok
    assert "repo broken" in msg


def test_worktree_remove_failure(tmp_path):
    state = tmp_path / ".ohwang"
    state.mkdir()
    (state / "worktree.json").write_text(
        json.dumps({"branch": "b", "path": str(tmp_path / "wt")}), encoding="utf-8"
    )
    mgr = WorktreeManager(str(tmp_path))
    mgr._git = lambda *a, **k: (1, "", "remove failed")
    ok, msg = mgr.remove()
    assert not ok
    assert "remove failed" in msg


def test_worktree_list_failure(tmp_path):
    mgr = WorktreeManager(str(tmp_path))
    mgr._git = lambda *a, **k: (1, "", "list failed")
    out = mgr.list()
    assert "list failed" in out


def test_worktree_git_timeout(monkeypatch, tmp_path):
    import subprocess

    from ohwang.services import worktree as wt

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("git", timeout=60)

    monkeypatch.setattr(wt.subprocess, "run", boom)
    mgr = WorktreeManager(str(tmp_path))
    code, _, err = mgr._git("x")
    assert code == 1
    assert "timed out" in err


# ---------- registry ----------

def test_registry_iter_and_contains():
    from ohwang.tools.base import BaseTool, ToolResult

    class T(BaseTool):
        name = "t"

        def execute(self, input):
            return ToolResult(content="ok")

    reg = ToolRegistry()
    reg.register(T())
    assert "t" in reg
    assert [x.name for x in reg] == ["t"]
    assert len(reg) == 1
    assert reg.get("nope") is None


# ---------- compact: _serialize branches + empty summary ----------

def test_compact_serialize_tool_blocks():
    from ohwang.services.compact import Compactor

    msgs = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "bash", "input": {"command": "ls"}}
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": "file1\nfile2", "tool_use_id": "t1"}
            ],
        },
        {"role": "user", "content": 42},  # non-list, non-str -> skipped
    ]
    out = Compactor._serialize(msgs)
    assert "tool_use bash" in out
    assert "tool_result" in out
    assert "{'command': 'ls'}" in out


def test_compact_falls_back_on_empty_summary():
    from ohwang.services.compact import Compactor
    from tests.helpers import ScriptedProvider

    c = Compactor(threshold_tokens=1, keep_recent=2)
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "a"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "b"}]},
        {"role": "user", "content": [{"type": "text", "text": "c"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "d"}]},
    ]
    provider = ScriptedProvider([[{"type": "text", "text": "   "}]])
    assert c.compact(msgs, provider, "system") is msgs


# ---------- default_tools skill registration ----------

def test_default_tools_registers_skill_tool():
    from ohwang.skills.loader import SkillLoader
    from ohwang.tools import default_tools

    loader = SkillLoader(tempfile.mkdtemp())
    loader.load_all()
    reg = default_tools(skill_loader=loader)
    assert "skill" in reg


# ---------- base tool specs / ToolResult ----------

def test_tool_result_to_block():
    from ohwang.tools.base import BaseTool, ToolResult

    r = ToolResult(content="hi", is_error=True)
    block = r.to_block()
    assert block["type"] == "tool_result"
    assert block["content"] == "hi"
    assert block["is_error"] is True

    class T(BaseTool):
        name = "spec_tool"
        description = "desc"
        input_schema = {"type": "object"}

        def execute(self, input):
            return ToolResult(content="ok")

    spec = T().to_spec()
    assert spec["name"] == "spec_tool"
    assert spec["description"] == "desc"
    assert spec["input_schema"] == {"type": "object"}


def test_registry_rejects_empty_name():
    from ohwang.tools.base import BaseTool, ToolResult

    class T(BaseTool):
        name = ""

        def execute(self, input):
            return ToolResult(content="ok")

    reg = ToolRegistry()
    try:
        reg.register(T())
        raise AssertionError("should have raised")
    except ValueError:
        pass


# ---------- file_read / file_write OSError branches ----------

def test_file_read_cannot_read(monkeypatch, tmp_path):
    from ohwang.tools.file_read import FileReadTool

    p = tmp_path / "f.txt"
    p.write_text("abc", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr("builtins.open", boom)
    r = FileReadTool().execute({"file_path": str(p)})
    assert r.is_error
    assert "Cannot read file" in r.content


def test_file_write_cannot_write(monkeypatch, tmp_path):
    from ohwang.tools.file_write import FileWriteTool

    p = tmp_path / "f.txt"

    def boom(*a, **k):
        raise OSError("readonly")

    monkeypatch.setattr("builtins.open", boom)
    r = FileWriteTool().execute({"file_path": str(p), "content": "x"})
    assert r.is_error
    assert "Cannot write file" in r.content


# ---------- policy: corrupt json ----------

def test_policy_load_corrupt_json(tmp_path):
    from ohwang.services.policy import PolicyLimits

    (tmp_path / ".ohwang").mkdir(exist_ok=True)
    (tmp_path / ".ohwang" / "policy.json").write_text("{bad", encoding="utf-8")
    p = PolicyLimits.load(str(tmp_path))
    assert p.max_tool_calls == 200
    assert p.per_tool == {}


# ---------- settings: unknown action ----------

def test_settings_unknown_action_raises(tmp_path):
    from ohwang.services.settings import update_settings

    try:
        update_settings(str(tmp_path), "bogus", "k", "v")
        raise AssertionError("should have raised")
    except ValueError:
        pass


# ---------- scheduler: 'a-b/step' and bare 'a' ranges ----------

def test_cron_range_with_step_and_open_bounds():
    from ohwang.services.scheduler import cron_matches

    assert cron_matches("0 8-10/2 * * *", 0, 8, 1, 1, 0) is True
    assert cron_matches("0 8-10/2 * * *", 0, 9, 1, 1, 0) is False
    assert cron_matches("0 -/5 * * *", 0, 5, 1, 1, 0) is True


# ---------- browser close swallow errors ----------

def test_browser_close_swallows_close_and_stop_errors(monkeypatch, tmp_path):
    from tests.test_browser import _make_session
    import tests.test_browser as tb

    browser = tb._FakeBrowser()

    def boom_close():
        raise RuntimeError("close boom")

    browser.close = boom_close
    session, browser = _make_session(monkeypatch, tmp_path, browser)
    session.navigate("https://example.com")
    session._pw.stop = lambda: (_ for _ in ()).throw(RuntimeError("stop boom"))
    session.close()  # must not raise
    assert session._page is None


# ---------- hooks: post cmd tool filter, run_cmd exception ----------

def test_hooks_post_cmd_filter_and_run_cmd_exception(tmp_path):
    from ohwang.services.hooks import HookManager

    (tmp_path / ".ohwang").mkdir(exist_ok=True)
    (tmp_path / ".ohwang" / "hooks.json").write_text(
        json.dumps(
            {
                "post_tool_use": [{"tool": "bash", "command": "echo x"}],
                "notif": [{"command": "echo y"}],
            }
        ),
        encoding="utf-8",
    )
    hooks = HookManager(str(tmp_path))
    hooks.load_json()
    hooks.run_post_tool("grep", {})  # filtered out, no error
    code, _ = hooks._run_cmd("definitely_not_a_command_xyz")
    assert code != 0


# ---------- lsp client stop/proc branches ----------

def test_lsp_client_stop_with_proc(monkeypatch):
    from ohwang.services import lsp as lsp_mod

    client = lsp_mod.LSPClient("cmd", [])
    client._proc = object()
    client._initialized = True
    client._send = lambda *a, **k: None
    client._notify = lambda *a, **k: None
    client.stop()
    assert client._proc is None
    assert client._initialized is False


def test_lsp_send_returns_result_and_none(monkeypatch):
    from ohwang.services import lsp as lsp_mod

    client = lsp_mod.LSPClient("cmd", [])
    client._proc = object()

    monkeypatch.setattr(lsp_mod, "_rpc_call", lambda proc, msg, timeout=30: {"result": {"ok": 1}})
    assert client._send("x", None) == {"ok": 1}

    monkeypatch.setattr(lsp_mod, "_rpc_call", lambda proc, msg, timeout=30: {"error": {"code": -1}})
    assert client._send("x", None) is None


def test_lsp_notify_writes_via_rpc(monkeypatch):
    from ohwang.services import lsp as lsp_mod

    called = []

    def fake_notify(proc, msg):
        called.append(msg)

    monkeypatch.setattr(lsp_mod, "_rpc_notify", fake_notify)
    client = lsp_mod.LSPClient("cmd", [])
    client._proc = object()
    client._notify("exit", None)
    assert called and called[0]["method"] == "exit"


def test_lsp_client_start_idempotent(monkeypatch):
    from ohwang.services import lsp as lsp_mod

    proc = object()
    client = lsp_mod.LSPClient("cmd", [])
    client._proc = proc
    client.start()  # already started -> no-op
    assert client._proc is proc


# ---------- mcp env merge / error response / stop ----------

def test_mcp_client_start_merges_env(monkeypatch):
    import subprocess
    from ohwang.services import mcp as mcp_mod

    captured = {}

    def fake_popen(*a, **k):
        captured["env"] = k["env"]
        captured["cmd"] = a[0]

        class _P:
            stdin = None
            stdout = None

            def terminate(self):
                pass

        return _P()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    client = mcp_mod.MCPClient("s", "cmd", [], env={"FOO": "bar"})
    monkeypatch.setattr(client, "_initialize", lambda: None)
    monkeypatch.setattr(client, "_read_loop", lambda: None)
    client.start()
    assert captured["env"].get("FOO") == "bar"
    assert captured["env"].get("PATH")  # inherited from os.environ


def test_mcp_send_raises_on_error_response():
    import sys
    import time
    from ohwang.services.mcp import MCPClient
    import pytest

    ERROR_SERVER = r'''
import json
import sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {}}) + "\n")
        sys.stdout.flush()
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -1, "message": "boom"}}) + "\n")
        sys.stdout.flush()
'''
    client = MCPClient("s", sys.executable, ["-c", ERROR_SERVER])
    client.start()
    time.sleep(0.3)
    with pytest.raises(RuntimeError, match="MCP error"):
        client._send("tools/list", {}, timeout=5)
    client.stop()


def test_mcp_stop_terminates_proc():
    from ohwang.services.mcp import MCPClient

    class _P:
        terminated = False

        def terminate(self):
            self.terminated = True

    client = MCPClient("s", "cmd", [])
    client._proc = _P()
    client._started = True
    client.stop()
    assert client._proc is None
    assert client._started is False


# ---------- memory store edge branches ----------

def test_memory_load_project_context_read_error(monkeypatch, tmp_path):
    from pathlib import Path
    from ohwang.services.memory import MemoryStore

    (tmp_path / "CLAUDE.md").write_text("ctx", encoding="utf-8")
    store = MemoryStore(str(tmp_path))

    def boom(self, *a, **k):
        raise OSError("perm")

    monkeypatch.setattr(Path, "read_text", boom)
    assert store.load_project_context() == ""


def test_memory_load_facts_errors(monkeypatch, tmp_path):
    from ohwang.services.memory import MemoryStore

    mem = tmp_path / ".ohwang" / "memory"
    mem.mkdir(parents=True)
    (mem / "facts.json").write_text("{bad json", encoding="utf-8")
    store = MemoryStore(str(tmp_path))
    assert store._load_facts() == {}


def test_memory_import_facts_skips_empty():
    from ohwang.services.memory import MemoryStore

    store = MemoryStore(tempfile.mkdtemp())
    added = store.import_facts(
        [
            {"key": "  ", "value": "x"},
            {"key": "k", "value": "  "},
            {"key": "ok", "value": "val", "tags": ["a", 3]},
        ]
    )
    assert added == 1
    assert store.get_fact("ok") == "val"


def test_memory_extract_parse_bracket_fallback():
    from ohwang.services.memory import MemoryExtractor

    assert MemoryExtractor._parse("here [{\"key\": \"a\", \"value\": \"b\"}] tail") == [
        {"key": "a", "value": "b"}
    ]
    assert MemoryExtractor._parse("no brackets here") == []
    assert MemoryExtractor._parse("[not json") == []


# ---------- skills frontmatter edge branches ----------

def test_skill_parse_frontmatter_scalars():
    from ohwang.skills.loader import _parse_frontmatter

    fm, body = _parse_frontmatter(
        "---\n"
        "name: x\n"
        "flag: true\n"
        "nope: null\n"
        "quoted: 'single'\n"
        "list: [a, b]\n"
        "nested:\n"
        "  - 1\n"
        "  - 2\n"
        "# comment line\n"
        "---\n"
        "Body"
    )
    assert fm["flag"] is True
    assert fm["nope"] == []
    assert fm["quoted"] == "single"
    assert fm["list"] == ["a", "b"]
    assert fm["nested"] == [1, 2]
    assert body == "Body"


def test_skill_parse_no_closing_frontmatter():
    from ohwang.skills.loader import _parse_frontmatter

    fm, body = _parse_frontmatter("---\nname: x\nno closing")
    assert fm == {}
    assert "no closing" in body


def test_skill_parse_empty_block_value():
    from ohwang.skills.loader import _parse_frontmatter

    fm, _ = _parse_frontmatter(
        "---\nallowed:\n  - bash\n---\nbody"
    )
    assert fm["allowed"] == ["bash"]


def test_skill_loader_skips_bad_skill_md(tmp_path):
    from ohwang.skills.loader import SkillLoader

    d = tmp_path / "bad" 
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname:\n---\n", encoding="utf-8")
    loader = SkillLoader(str(tmp_path))
    loader._load_dir(tmp_path, source="user")
    assert loader.get("bad") is None


def test_skill_loader_skips_unreadable_skill_md(monkeypatch, tmp_path):
    from pathlib import Path
    from ohwang.skills.loader import SkillLoader

    d = tmp_path / "good"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: good\ndescription: d\n---\nbody", encoding="utf-8")

    def boom(self, *a, **k):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", boom)
    loader = SkillLoader(str(tmp_path))
    loader._load_dir(tmp_path, source="user")
    assert loader.get("good") is None


def test_skill_loader_skips_invalid_json(tmp_path):
    from ohwang.skills.loader import SkillLoader

    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    loader = SkillLoader(str(tmp_path))
    loader._load_dir(tmp_path, source="user")
    assert loader.list_names() == []


def test_skill_describe_all_skips_empty_desc(tmp_path):
    from ohwang.skills.loader import SkillLoader

    d = tmp_path / "x"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: x\n---\nbody", encoding="utf-8")
    loader = SkillLoader(str(tmp_path))
    loader._load_dir(tmp_path, source="user")
    assert loader.describe_all() == []


# ---------- default_tools web_browser conditional ----------

def test_default_tools_registers_web_browser_when_enabled(monkeypatch):
    import types
    import sys
    from ohwang.tools import default_tools

    class _Flags:
        def is_enabled(self, name):
            return name == "web_browser"

    fake_pkg = types.ModuleType("playwright")
    fake_sync = types.ModuleType("playwright.sync_api")
    fake_sync.sync_playwright = lambda: None
    monkeypatch.setitem(sys.modules, "playwright", fake_pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync)
    monkeypatch.setitem(sys.modules, "playwright.driver", types.ModuleType("playwright.driver"))

    reg = default_tools(flags=_Flags())
    assert "browser_action" in reg


def test_default_tools_skips_web_browser_when_disabled():
    from ohwang.tools import default_tools

    class _Flags:
        def is_enabled(self, name):
            return False

    reg = default_tools(flags=_Flags())
    assert "browser_action" not in reg


def test_registry_specs_cached():
    from ohwang.tools.base import BaseTool, ToolResult
    from ohwang.tools.registry import ToolRegistry

    calls = {"n": 0}

    class T(BaseTool):
        name = "t"
        description = "desc"
        input_schema = {"type": "object", "properties": {}}

        def to_spec(self):
            calls["n"] += 1
            return {"name": self.name, "description": self.description}

        def execute(self, input):
            return ToolResult(content="ok")

    reg = ToolRegistry()
    reg.register(T())
    spec1 = reg.specs()
    spec2 = reg.specs()
    assert calls["n"] == 1
    assert spec1 == spec2


def test_registry_specs_invalidated_on_register():
    from ohwang.tools.base import BaseTool, ToolResult
    from ohwang.tools.registry import ToolRegistry

    class T(BaseTool):
        name = "t"
        description = "d"
        input_schema = {}

        def execute(self, input):
            return ToolResult(content="ok")

    class T2(BaseTool):
        name = "t2"
        description = "d2"
        input_schema = {}

        def execute(self, input):
            return ToolResult(content="ok")

    reg = ToolRegistry()
    reg.register(T())
    reg.specs()
    reg.register(T2())
    assert len(reg.specs()) == 2
    assert {s["name"] for s in reg.specs()} == {"t", "t2"}


def test_agent_system_cached_and_invalidated():
    from ohwang.agent import Agent
    from ohwang.config import Config
    from ohwang.tools.registry import ToolRegistry
    from ohwang.permissions import PermissionManager
    from ohwang.modes import Mode
    from ohwang.tools.base import BaseTool, ToolResult

    class T(BaseTool):
        name = "t"
        description = "d"
        input_schema = {}

        def execute(self, input):
            return ToolResult(content="ok")

    agent = Agent(
        provider=None,
        tools=ToolRegistry().register(T()),
        permissions=PermissionManager(mode=Mode.AUTO),
        config=Config(workdir=os.getcwd()).resolve(),
        system="SYSTEM_BASE",
    )
    s1 = agent._effective_system()
    s2 = agent._effective_system()
    assert s1 == s2 == "SYSTEM_BASE"
    agent._invalidate_system()
    assert agent._effective_system() == "SYSTEM_BASE"


def test_memory_render_context_cached(tmp_path):
    from ohwang.services.memory import MemoryStore

    ms = MemoryStore(str(tmp_path))
    ms.add_fact("k", "v1")
    first = ms.render_context()
    second = ms.render_context()
    assert "k" in first
    assert first == second
    ms.add_fact("k2", "v2")
    updated = ms.render_context()
    assert "k2" in updated


def test_memory_load_project_context_cached(tmp_path):
    from ohwang.services.memory import MemoryStore

    (tmp_path / "CLAUDE.md").write_text("project instructions", encoding="utf-8")
    ms = MemoryStore(str(tmp_path))
    assert ms.load_project_context() == "project instructions"
    (tmp_path / "CLAUDE.md").write_text("changed", encoding="utf-8")
    assert ms.load_project_context() == "changed"


def test_memory_render_context_caps_facts(tmp_path):
    from ohwang.services.memory import MemoryStore

    ms = MemoryStore(str(tmp_path))
    ms._max_facts_in_context = 3
    for i in range(5):
        ms.add_fact(f"key{i}", f"value{i}")
    ctx = ms.render_context()
    assert "key3" in ctx
    assert "key4" in ctx
    assert "key0" not in ctx
    assert "showing 3 of 5 facts" in ctx
