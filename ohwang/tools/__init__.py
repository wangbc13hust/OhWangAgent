from __future__ import annotations

import os

from .base import BaseTool, ToolResult
from .registry import ToolRegistry


def default_tools(
    todo_store=None,
    permissions=None,
    search_provider=None,
    ask_callback=None,
    agent_factory=None,
    workdir=None,
    scheduler=None,
    flags=None,
    usage=None,
    display_callback=None,
    iterations_getter=None,
    memory_store=None,
    skill_loader=None,
    task_store=None,
    hooks=None,
    shell_output_callback=None,
) -> ToolRegistry:
    """Build a registry with the core coding tools + extensions.

    Parameters:
      todo_store      — enables TodoWriteTool
      permissions     — enables enter/exit plan_mode tools
      search_provider — enables WebSearchTool (DuckDuckGo by default)
      ask_callback    — enables AskUserQuestionTool
      agent_factory   — enables AgentTool (sub-agent)
      workdir         — base dir for git worktree management
      scheduler       — enables cron_create/delete/list (proactive mode)
      flags           — FeatureFlags for gating web_browser
      usage           — UsageTracker for the brief tool
      display_callback — callable(str) for synthetic_output / send_user_file
      iterations_getter — callable() -> int for the brief tool
      memory_store    — enables memory_read/memory_write tools
      skill_loader    — enables the skill tool
      task_store      — enables task_create/get/update/list/stop/output tools
      shell_output_callback — callable(name, text) for live bash/powershell
        output forwarding (interactive terminals only)
    """
    from .bash import BashTool
    from .file_edit import FileEditTool
    from .file_read import FileReadTool
    from .file_write import FileWriteTool
    from .file_diff import FileDiffTool, FilePreviewEditTool
    from .multi_edit import MultiEditTool
    from .glob import GlobTool
    from .grep import GrepTool
    from .powershell import PowerShellTool
    from .tool_search import ToolSearchTool
    from .sleep import SleepTool
    from .config import ConfigTool
    from .synthetic_output import SyntheticOutputTool
    from .brief import BriefTool
    from .snip import SnipTool
    from .send_user_file import SendUserFileTool
    from .verify_plan import VerifyPlanExecutionTool
    from .web_fetch import WebFetchTool
    from .web_search import WebSearchTool

    registry = ToolRegistry()
    for tool in (
        BashTool(output_callback=shell_output_callback),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        GrepTool(),
        GlobTool(),
        WebFetchTool(),
        PowerShellTool(output_callback=shell_output_callback),
        SleepTool(),
    ):
        registry.register(tool)

    registry.register(ToolSearchTool(registry))
    registry.register(ConfigTool(workdir or os.getcwd(), permissions))
    registry.register(SyntheticOutputTool(display_callback))
    registry.register(BriefTool(usage, todo_store, iterations_getter))
    registry.register(SnipTool(workdir or os.getcwd()))
    registry.register(SendUserFileTool(display_callback))
    registry.register(VerifyPlanExecutionTool())
    registry.register(FileDiffTool())
    registry.register(FilePreviewEditTool())
    registry.register(MultiEditTool())

    if search_provider is not None:
        registry.register(WebSearchTool(search_provider))
    else:
        from ..services.search import BingSearch, DuckDuckGoSearch, make_search_provider
        sp = make_search_provider()
        if sp is not None:
            fallbacks = []
            for candidate in (BingSearch(), DuckDuckGoSearch()):
                if candidate.name != sp.name:
                    fallbacks.append(candidate)
            registry.register(WebSearchTool(sp, fallbacks))

    if todo_store is not None:
        from .todo import TodoWriteTool
        registry.register(TodoWriteTool(todo_store))

    if task_store is not None:
        from .tasks import (
            TaskCreateTool,
            TaskGetTool,
            TaskListTool,
            TaskOutputTool,
            TaskStopTool,
            TaskUpdateTool,
        )
        registry.register(TaskCreateTool(task_store))
        registry.register(TaskGetTool(task_store))
        registry.register(TaskUpdateTool(task_store))
        registry.register(TaskListTool(task_store))
        registry.register(TaskStopTool(task_store))
        registry.register(TaskOutputTool(task_store))

    if memory_store is not None:
        from .memory import MemoryReadTool, MemoryWriteTool
        registry.register(MemoryReadTool(memory_store))
        registry.register(MemoryWriteTool(memory_store))

    if skill_loader is not None:
        from ..skills.tool import SkillTool
        registry.register(SkillTool(skill_loader))

    if permissions is not None:
        from .plan_mode import EnterPlanModeTool, ExitPlanModeTool
        registry.register(EnterPlanModeTool(permissions))
        registry.register(ExitPlanModeTool(permissions))

    if ask_callback is not None:
        from .ask_user import AskUserQuestionTool
        registry.register(AskUserQuestionTool(ask_callback))

    if agent_factory is not None:
        from .agent_tool import AgentTool
        registry.register(AgentTool(agent_factory, hooks=hooks))

    from ..services.worktree import WorktreeManager
    from .worktree import EnterWorktreeTool, ExitWorktreeTool
    wm = WorktreeManager(workdir or os.getcwd())
    registry.register(EnterWorktreeTool(wm))
    registry.register(ExitWorktreeTool(wm))

    if scheduler is not None:
        from .schedule import CronCreateTool, CronDeleteTool, CronListTool
        registry.register(CronCreateTool(scheduler))
        registry.register(CronDeleteTool(scheduler))
        registry.register(CronListTool(scheduler))

    if flags is not None and flags.is_enabled("web_browser"):
        try:
            from ..services.browser import BrowserSession
            from .web_browser import WebBrowserTool
        except ImportError:
            pass
        else:
            try:
                import playwright  # noqa: F401
            except ImportError:
                pass
            else:
                registry.register(WebBrowserTool(BrowserSession(workdir=workdir)))

    return registry


__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "default_tools"]
