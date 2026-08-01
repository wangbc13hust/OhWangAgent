import json
import os
import tempfile

from ohwang.plugins.loader import Plugin, PluginLoader
from ohwang.tools.registry import ToolRegistry


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


def test_plugin_dataclass():
    p = Plugin(name="test", description="desc", entry_point="mod:fn", tools=["x"])
    assert p.name == "test"
    assert p.entry_point == "mod:fn"
