from .base import BaseTool, ToolResult
from .registry import ToolRegistry


def default_tools() -> ToolRegistry:
    """Build a registry with the core coding tools."""
    from .bash import BashTool
    from .file_edit import FileEditTool
    from .file_read import FileReadTool
    from .file_write import FileWriteTool
    from .glob import GlobTool
    from .grep import GrepTool

    registry = ToolRegistry()
    for tool in (
        BashTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        GrepTool(),
        GlobTool(),
    ):
        registry.register(tool)
    return registry


__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "default_tools"]
