from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..tools.base import BaseTool
    from ..tools.registry import ToolRegistry


@dataclass
class Plugin:
    name: str
    description: str
    entry_point: str
    tools: list[str] = field(default_factory=list)
    source: str = ""


class PluginLoader:
    """Load plugins from .ohwang/plugins/*.json.

    Plugin JSON schema:
      {
        "name": "my_plugin",
        "description": "Does X and Y",
        "entry_point": "my_package.ohwang_plugin:register",
        "tools": ["my_tool"]
      }

    The entry_point function receives (registry, config) and can register
    tools, commands, or providers.
    """

    def __init__(self, workdir: str | Path) -> None:
        self.plugin_dir = Path(workdir) / ".ohwang" / "plugins"
        self._plugins: dict[str, Plugin] = {}

    def load_all(self) -> dict[str, Plugin]:
        self._plugins.clear()
        if not self.plugin_dir.is_dir():
            return self._plugins
        for f in sorted(self.plugin_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            name = data.get("name", f.stem)
            self._plugins[name] = Plugin(
                name=name,
                description=data.get("description", ""),
                entry_point=data.get("entry_point", ""),
                tools=data.get("tools", []),
                source="user",
            )
        return self._plugins

    def register_all(self, registry: "ToolRegistry") -> list[str]:
        """Load and activate all plugins, registering their tools."""
        self.load_all()
        added: list[str] = []
        for plugin in self._plugins.values():
            if not plugin.entry_point:
                continue
            try:
                registered = self._activate(plugin, registry)
                added.extend(registered)
            except Exception:
                continue
        return added

    def _activate(self, plugin: Plugin, registry: "ToolRegistry") -> list[str]:
        module_path, _, func_name = plugin.entry_point.partition(":")
        module = importlib.import_module(module_path)
        func = getattr(module, func_name or "register")
        result = func(registry)
        if isinstance(result, list):
            return [t.name if hasattr(t, "name") else str(t) for t in result]
        return plugin.tools

    def get(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)

    def list_names(self) -> list[str]:
        return list(self._plugins)
