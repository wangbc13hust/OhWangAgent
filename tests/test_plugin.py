import json
import os
import tempfile

from ohwang.plugins.loader import Plugin, PluginLoader
from ohwang.tools.registry import ToolRegistry

FAKE_PLUGIN_MODULE = '''
def register(registry):
    class FakeTool:
        name = "fake_tool"
        def to_spec(self):
            return {"name": "fake_tool"}
    registry.register(FakeTool())
    return [FakeTool()]
'''


def test_plugin_loader_no_dir():
    d = tempfile.mkdtemp()
    loader = PluginLoader(d)
    plugins = loader.load_all()
    assert plugins == {}


def test_plugin_loader_with_config():
    d = tempfile.mkdtemp()
    plugin_dir = os.path.join(d, ".ohwang", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "my_plugin.json"), "w", encoding="utf-8") as f:
        json.dump({
            "name": "my_plugin",
            "description": "A test plugin",
            "entry_point": "",
            "tools": ["custom_tool"],
        }, f)

    loader = PluginLoader(d)
    plugins = loader.load_all()
    assert "my_plugin" in plugins
    assert plugins["my_plugin"].description == "A test plugin"
    assert "custom_tool" in plugins["my_plugin"].tools
    assert plugins["my_plugin"].source == "user"


def test_plugin_loader_invalid_json_skipped():
    d = tempfile.mkdtemp()
    plugin_dir = os.path.join(d, ".ohwang", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "bad.json"), "w", encoding="utf-8") as f:
        f.write("{not json")
    with open(os.path.join(plugin_dir, "good.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "good", "entry_point": ""}, f)
    loader = PluginLoader(d)
    plugins = loader.load_all()
    assert "good" in plugins


def test_plugin_register_all_no_entry_point():
    d = tempfile.mkdtemp()
    plugin_dir = os.path.join(d, ".ohwang", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "noop.json"), "w", encoding="utf-8") as f:
        json.dump({
            "name": "noop",
            "description": "No-op plugin",
            "entry_point": "",
            "tools": [],
        }, f)

    loader = PluginLoader(d)
    registry = ToolRegistry()
    added = loader.register_all(registry)
    assert added == []


def test_plugin_register_all_activates_entry_point():
    d = tempfile.mkdtemp()
    plugin_dir = os.path.join(d, ".ohwang", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    mod_name = "_ohwang_test_plugin_mod"
    import sys
    sys.path.insert(0, d)
    try:
        with open(os.path.join(d, f"{mod_name}.py"), "w", encoding="utf-8") as f:
            f.write(FAKE_PLUGIN_MODULE)
        with open(os.path.join(plugin_dir, "active.json"), "w", encoding="utf-8") as f:
            json.dump({
                "name": "active",
                "entry_point": f"{mod_name}:register",
                "tools": ["fake_tool"],
            }, f)
        loader = PluginLoader(d)
        registry = ToolRegistry()
        added = loader.register_all(registry)
        assert added == ["fake_tool"]
        assert "fake_tool" in registry
    finally:
        sys.path.remove(d)
        sys.modules.pop(mod_name, None)


def test_plugin_register_all_skips_failing_entry_point():
    d = tempfile.mkdtemp()
    plugin_dir = os.path.join(d, ".ohwang", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "bad.json"), "w", encoding="utf-8") as f:
        json.dump({
            "name": "bad",
            "entry_point": "definitely_not_a_real_module:register",
        }, f)
    loader = PluginLoader(d)
    registry = ToolRegistry()
    added = loader.register_all(registry)
    assert added == []


def test_plugin_activate_returns_plugin_tools_when_no_list():
    d = tempfile.mkdtemp()
    mod_name = "_ohwang_test_plugin_tools_mod"
    import sys
    sys.path.insert(0, d)
    try:
        with open(os.path.join(d, f"{mod_name}.py"), "w", encoding="utf-8") as f:
            f.write("def register(registry):\n    return None\n")
        loader = PluginLoader(d)
        registry = ToolRegistry()
        p = Plugin(name="x", description="", entry_point=f"{mod_name}:register", tools=["t1"])
        assert loader._activate(p, registry) == ["t1"]
    finally:
        sys.path.remove(d)
        sys.modules.pop(mod_name, None)


def test_plugin_get_and_list():
    d = tempfile.mkdtemp()
    plugin_dir = os.path.join(d, ".ohwang", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "abc.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "abc", "entry_point": ""}, f)
    loader = PluginLoader(d)
    loader.load_all()
    assert loader.get("abc") is not None
    assert loader.list_names() == ["abc"]


def test_plugin_dataclass():
    p = Plugin(name="test", description="desc", entry_point="mod:fn", tools=["x"])
    assert p.name == "test"
    assert p.entry_point == "mod:fn"
