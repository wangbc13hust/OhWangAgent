"""Layered memory: user/global layer, type field, relevance-ranked rendering.

These are the new capabilities added on top of the existing single-layer
project memory; the old behavior is covered in tests/test_memory.py.
"""

import json

from ohwang.services.memory import MemoryStore


def _store(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    return project, tmp_path / "home"


def test_memory_add_fact_user_scope_writes_to_home_dir(tmp_path):
    project, home = _store(tmp_path)
    store = MemoryStore(str(project), home_dir=str(home))
    store.add_fact("lang", "prefers Chinese replies", scope="user")
    assert store.get_fact("lang", scope="user") == "prefers Chinese replies"
    # project layer must NOT contain it
    assert store.get_fact("lang") is None
    # user file written under home, not the project dir
    assert (home / ".ohwang" / "memory" / "facts.json").is_file()
    proj_facts = project / ".ohwang" / "memory" / "facts.json"
    if proj_facts.is_file():
        assert "lang" not in json.loads(proj_facts.read_text(encoding="utf-8"))


def test_memory_user_layer_disabled_by_default(tmp_path):
    store = MemoryStore(str(tmp_path))
    assert store.user_layer_enabled is False
    store.add_fact("k", "v", scope="user")  # falls back to project, never dropped
    assert store.get_fact("k") == "v"
    assert store.get_fact("k", scope="user") is None


def test_memory_migration_old_rows_default_project(tmp_path):
    mem = tmp_path / ".ohwang" / "memory"
    mem.mkdir(parents=True)
    (mem / "facts.json").write_text(
        '{"legacy": {"value": "v", "tags": []}}', encoding="utf-8"
    )
    store = MemoryStore(str(tmp_path))
    assert store.list_facts()[0]["type"] == "project"


def test_memory_render_context_merges_layers(tmp_path):
    project, home = _store(tmp_path)
    store = MemoryStore(str(project), home_dir=str(home))
    store.add_fact("p", "project fact", scope="project")
    store.add_fact("u", "user fact", scope="user")
    ctx = store.render_context()
    assert "# User Memory" in ctx
    assert "# Project Memory" in ctx
    assert ctx.index("# User Memory") < ctx.index("# Project Memory")


def test_memory_render_context_ranked_prioritizes_key(tmp_path):
    store = MemoryStore(str(tmp_path))
    store.add_fact("build_cmd", "npm run build")
    store.add_fact("deploy", "k8s rollout", tags=["build"])
    ctx = store.render_context(query="build")
    lines = ctx.splitlines()
    build_idx = next(i for i, l in enumerate(lines) if "build_cmd" in l)
    deploy_idx = next(i for i, l in enumerate(lines) if "deploy" in l)
    assert build_idx < deploy_idx  # key hit outweighs tag hit


def test_memory_render_context_ranked_caps(tmp_path):
    store = MemoryStore(str(tmp_path))
    for i in range(15):
        store.add_fact(f"match{i}", f"value {i}")
    ctx = store.render_context(query="value")
    assert ctx.count("- **match") <= 10


def test_memory_render_context_ranked_cjk_value_match(tmp_path):
    store = MemoryStore(str(tmp_path))
    store.add_fact("meeting_day", "周会每周三")
    store.add_fact("other", "unrelated stuff")
    ctx = store.render_context(query="周会")
    assert "meeting_day" in ctx
    assert "other" not in ctx


def test_memory_user_write_invalidates_context_cache(tmp_path):
    project, home = _store(tmp_path)
    store = MemoryStore(str(project), home_dir=str(home))
    store.add_fact("p", "project fact")
    assert "user fact" not in store.render_context()
    store.add_fact("u", "user fact", scope="user")
    assert "user fact" in store.render_context()


def test_memory_search_scope_user(tmp_path):
    project, home = _store(tmp_path)
    store = MemoryStore(str(project), home_dir=str(home))
    store.add_fact("shared", "alpha", scope="project")
    store.add_fact("shared", "beta", scope="user")
    res = store.search_facts("beta", scope="user")
    assert len(res) == 1
    assert res[0]["type"] == "user"
    assert len(store.search_facts("alpha")) == 1  # project-only hit in merged search
