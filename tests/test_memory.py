import os
import tempfile

from ohwang.services.memory import MemoryStore
from ohwang.tools.memory import MemoryReadTool, MemoryWriteTool


def test_memory_add_and_get():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("auth_pattern", "JWT + refresh tokens", tags=["auth", "security"])
    val = store.get_fact("auth_pattern")
    assert val == "JWT + refresh tokens"


def test_memory_search():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("build_cmd", "npm run build", tags=["build"])
    store.add_fact("test_cmd", "npm test", tags=["test"])
    results = store.search_facts("npm")
    assert len(results) == 2


def test_memory_search_by_tag():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("x", "val1", tags=["auth"])
    store.add_fact("y", "val2", tags=["build"])
    results = store.search_facts("auth")
    assert len(results) == 1
    assert results[0]["key"] == "x"


def test_memory_delete():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("temp", "will be deleted")
    assert store.delete_fact("temp") is True
    assert store.get_fact("temp") is None
    assert store.delete_fact("nonexistent") is False


def test_memory_list_facts():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("a", "1")
    store.add_fact("b", "2")
    facts = store.list_facts()
    assert len(facts) == 2


def test_memory_load_claude_md():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write("# Project\nUse pytest for testing.")
    store = MemoryStore(d)
    ctx = store.load_project_context()
    assert "pytest" in ctx


def test_memory_render_context():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write("# Project\nHello")
    store = MemoryStore(d)
    store.add_fact("key1", "value1")
    ctx = store.render_context()
    assert "Hello" in ctx
    assert "key1" in ctx


def test_memory_render_context_reflects_project_file_changes(tmp_path):
    store = MemoryStore(str(tmp_path))
    assert store.render_context() == ""
    (tmp_path / "CLAUDE.md").write_text("alpha", encoding="utf-8")
    assert "alpha" in store.render_context()
    (tmp_path / "CLAUDE.md").write_text("beta", encoding="utf-8")
    assert "beta" in store.render_context()


def test_memory_read_tool():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("arch", "microservices")
    tool = MemoryReadTool(store)
    r = tool.execute({})
    assert r.is_error is False
    assert "microservices" in r.content


def test_memory_read_tool_with_query():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("db_url", "postgres://localhost:5432")
    tool = MemoryReadTool(store)
    r = tool.execute({"query": "postgres"})
    assert r.is_error is False
    assert "db_url" in r.content


def test_memory_write_tool():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    tool = MemoryWriteTool(store)
    r = tool.execute({"key": "style", "value": "use black formatter", "tags": ["style"]})
    assert r.is_error is False
    assert store.get_fact("style") == "use black formatter"


def test_memory_write_tool_user_scope(tmp_path):
    home = tmp_path / "home"
    store = MemoryStore(str(tmp_path), home_dir=str(home))
    tool = MemoryWriteTool(store)
    r = tool.execute({"key": "k", "value": "v", "scope": "user"})
    assert r.is_error is False
    assert store.get_fact("k", scope="user") == "v"


def test_memory_read_tool_scope_user(tmp_path):
    home = tmp_path / "home"
    store = MemoryStore(str(tmp_path), home_dir=str(home))
    store.add_fact("pk", "project value", scope="project")
    store.add_fact("uk", "user value", scope="user")
    tool = MemoryReadTool(store)
    r = tool.execute({"query": "value", "scope": "user"})
    assert r.is_error is False
    assert "uk" in r.content
    assert "pk" not in r.content


def test_memory_persistence():
    d = tempfile.mkdtemp()
    store1 = MemoryStore(d)
    store1.add_fact("persist", "this survives restart")
    store2 = MemoryStore(d)
    assert store2.get_fact("persist") == "this survives restart"


def test_memory_facts_cache_invalidated_on_write():
    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("k1", "v1")
    assert "k1" in store.render_context()
    store.add_fact("k2", "v2")
    ctx = store.render_context()
    assert "k2" in ctx and "v2" in ctx


def test_memory_facts_cache_matches_mtime():
    import time

    d = tempfile.mkdtemp()
    store = MemoryStore(d)
    store.add_fact("k1", "v1")
    first = store._load_facts()
    assert store._load_facts() is first
    time.sleep(0.01)
    store.add_fact("k2", "v2")
    second = store._load_facts()
    assert "k2" in second
