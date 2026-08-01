from .base import BaseTool, ToolResult
from .registry import ToolRegistry


def default_tools(todo_store=None, permissions=None) -> ToolRegistry:
    """Build a registry with the core coding tools.

    Optionally wire stateful tools that need shared handles:
      todo_store   — enables the TodoWriteTool
      permissions  — enables enter/exit plan_mode tools
    """
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

    if todo_store is not None:
        from .todo import TodoWriteTool

        registry.register(TodoWriteTool(todo_store))

    if permissions is not None:
        from .plan_mode import EnterPlanModeTool, ExitPlanModeTool

        registry.register(EnterPlanModeTool(permissions))
        registry.register(ExitPlanModeTool(permissions))

    return registry


__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "default_tools"]
