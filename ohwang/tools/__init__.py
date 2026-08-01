from .base import BaseTool, ToolResult
from .registry import ToolRegistry


def default_tools(
    todo_store=None,
    permissions=None,
    search_provider=None,
    ask_callback=None,
    agent_factory=None,
) -> ToolRegistry:
    """Build a registry with the core coding tools + P1 extensions.

    Parameters:
      todo_store      — enables TodoWriteTool
      permissions     — enables enter/exit plan_mode tools
      search_provider — enables WebSearchTool (DuckDuckGo by default)
      ask_callback    — enables AskUserQuestionTool
      agent_factory   — enables AgentTool (sub-agent)
    """
    from .bash import BashTool
    from .file_edit import FileEditTool
    from .file_read import FileReadTool
    from .file_write import FileWriteTool
    from .glob import GlobTool
    from .grep import GrepTool
    from .web_fetch import WebFetchTool
    from .web_search import WebSearchTool

    registry = ToolRegistry()
    for tool in (
        BashTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        GrepTool(),
        GlobTool(),
        WebFetchTool(),
    ):
        registry.register(tool)

    if search_provider is not None:
        registry.register(WebSearchTool(search_provider))
    else:
        from ..services.search import make_search_provider
        sp = make_search_provider()
        if sp is not None:
            registry.register(WebSearchTool(sp))

    if todo_store is not None:
        from .todo import TodoWriteTool
        registry.register(TodoWriteTool(todo_store))

    if permissions is not None:
        from .plan_mode import EnterPlanModeTool, ExitPlanModeTool
        registry.register(EnterPlanModeTool(permissions))
        registry.register(ExitPlanModeTool(permissions))

    if ask_callback is not None:
        from .ask_user import AskUserQuestionTool
        registry.register(AskUserQuestionTool(ask_callback))

    if agent_factory is not None:
        from .agent_tool import AgentTool
        registry.register(AgentTool(agent_factory))

    return registry


__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "default_tools"]
