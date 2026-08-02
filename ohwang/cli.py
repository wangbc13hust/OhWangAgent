from __future__ import annotations

import argparse
import os
import shlex
import sys
from threading import Lock

from .agent import Agent
from .config import PROVIDER_PRESETS, Config
from .flags import FeatureFlags
from .modes import Mode
from .permissions import PermissionManager
from .prompts import build_system_prompt
from .providers import create_provider
from .services import (
    Compactor,
    HookManager,
    MemoryExtractor,
    MemoryStore,
    PolicyLimits,
    SessionStore,
    SessionSummarizer,
    UsageTracker,
)
from .services.cost import calculate_cost, format_cost
from .services.guards import dangerous_command_hook
from .services.scheduler import Scheduler
from .services.settings import load_settings
from .services.window import effective_context_window
from .tools import default_tools
from .tools.tasks import TaskStore
from .tools.todo import TodoStore
from .tui import Renderer, read_stdin_line, setup_utf8


def _load_env(workdir: str) -> None:
    """Load KEY=VALUE pairs from <workdir>/.env into os.environ (no override).

    Also falls back to the package root's .env so keys remain available when
    running with a --workdir that lacks its own .env file. Lightweight
    replacement for python-dotenv: handles blank lines, comments, and optional
    quotes; does not support variable expansion or multiline values.
    """
    candidates = [workdir, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    for base in candidates:
        path = os.path.join(base, ".env")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if (
                        len(value) >= 2
                        and value[0] == value[-1]
                        and value[0] in ("'", '"')
                    ):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass


def _prepare_workdir(args: argparse.Namespace) -> None:
    """chdir into --workdir and normalize it to an absolute path.

    Keeps the tool layer (relative paths resolve against the new cwd) and the
    service layer (.ohwang/ data dirs built from config.workdir) consistent: a
    relative --workdir would otherwise be re-resolved against the already-changed
    cwd, producing nested data directories like sub/sub/.ohwang/.
    """
    if args.workdir:
        os.chdir(args.workdir)
        args.workdir = os.getcwd()


def _warn_noninteractive_approval(args: argparse.Namespace) -> None:
    """Warn when a non-interactive one-shot run will silently deny 'ask' tools.

    Without -y/--auto-approve, every ask-permission tool defaults to deny when
    stdin is a pipe, which surprises scripted/CI callers and can send the model
    into a permission-denial retry loop. --plan is fine (read-only intent).
    """
    if args.prompt and not args.auto_approve and not args.plan:
        try:
            if not sys.stdin.isatty():
                sys.stderr.write(
                    "Warning: non-interactive one-shot without -y — 'ask' tools "
                    "will default to deny. Pass -y to auto-approve, or --plan "
                    "for read-only research.\n"
                )
        except Exception:
            pass


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ohwang",
        description="OhWangAgent — an interactive CLI office agent (documents, research, tasks, and code).",
    )
    p.add_argument("--provider", choices=list(PROVIDER_PRESETS), default="zhipu")
    p.add_argument("--model", default=None, help="Model id (overrides preset)")
    p.add_argument("--api-key", default=None, help="API key (else read from env)")
    p.add_argument(
        "--base-url", default=None, help="OpenAI-compatible endpoint (openai provider)"
    )
    p.add_argument("--max-tokens", type=int, default=16384)
    p.add_argument(
        "-y",
        "--auto-approve",
        action="store_true",
        help="Auto-approve every tool call (AUTO mode)",
    )
    p.add_argument(
        "--plan",
        action="store_true",
        help="Start in PLAN mode (read-only, no writes/bash)",
    )
    p.add_argument(
        "--compact-threshold",
        type=int,
        default=None,
        help="Token estimate threshold to trigger context compaction "
        "(default: derived from the model's context window)",
    )
    p.add_argument(
        "--context-window",
        type=int,
        default=None,
        help="Model context window in tokens (default: provider preset; "
        "overridable via OHWANG_MAX_CONTEXT_TOKENS)",
    )
    p.add_argument("--workdir", default=None, help="Working directory")
    p.add_argument(
        "--no-mcp",
        action="store_true",
        help="Do not load MCP servers from .ohwang/mcp.json",
    )
    p.add_argument(
        "--no-proactive",
        action="store_true",
        help="Do not start the proactive cron scheduler",
    )
    p.add_argument(
        "prompt", nargs="?", default=None, help="Run one prompt then exit (non-REPL)"
    )
    return p.parse_args(argv)


def build_agent(args: argparse.Namespace, run_lock: Lock):
    config = Config(
        provider=args.provider,
        model=args.model or "",
        api_key=args.api_key or "",
        max_tokens=args.max_tokens,
        auto_approve=args.auto_approve,
        plan=args.plan,
        compact_threshold=args.compact_threshold,
        workdir=os.path.abspath(args.workdir or os.getcwd()),
        context_window=getattr(args, "context_window", None),
    ).resolve()

    if not config.api_key:
        env_var = PROVIDER_PRESETS.get(config.provider, {}).get("env", "")
        sys.stderr.write(f"Error: no API key. Set ${env_var} or pass --api-key.\n")
        sys.exit(2)

    provider = create_provider(config, base_url=args.base_url)
    renderer = Renderer()
    flags = FeatureFlags(config.workdir)

    if config.plan:
        mode = Mode.PLAN
    elif config.auto_approve:
        mode = Mode.AUTO
    else:
        mode = Mode.DEFAULT

    settings = load_settings(config.workdir)
    permissions = PermissionManager(
        mode=mode,
        ask_callback=renderer.ask,
        allow=settings["allow"],
        ask=settings["ask"],
        deny=settings["deny"],
    )
    todo_store = TodoStore()
    task_store = TaskStore(config.workdir)
    usage = UsageTracker()
    memory_store = MemoryStore(
        config.workdir,
        home_dir=os.environ.get("OHWANG_HOME") or os.path.expanduser("~"),
    )
    memory_extractor = (
        MemoryExtractor(memory_store) if flags.is_enabled("memory") else None
    )
    session_summarizer = (
        SessionSummarizer() if flags.is_enabled("session") else None
    )
    skill_loader = None
    if flags.is_enabled("skill"):
        from .skills.loader import SkillLoader
        skill_loader = SkillLoader(config.workdir)
        skill_loader.load_all()

    system_prompt = build_system_prompt(
        config.workdir,
        skills=skill_loader.describe_all() if skill_loader is not None else None,
    )

    scheduler = Scheduler(
        runner=None, state_file=os.path.join(config.workdir, ".ohwang", "cron.json")
    )

    def _run_locked(prompt: str) -> str:
        with run_lock:
            try:
                return agent.run(
                    prompt,
                    on_text=renderer.stream_text,
                    on_tool_call=renderer.tool_call,
                    on_tool_result=renderer.tool_result,
                    on_compact=lambda b, a: renderer.warn(
                        f"Context compacted: {b} -> {a} messages."
                    ),
                )
            except Exception as exc:
                renderer.warn(f"Background task error: {exc}")
                return ""

    scheduler._runner = _run_locked

    def _agent_factory():
        # Sub-agents get their own AUTO PermissionManager so plan-mode / config
        # tools inside a sub-agent can never mutate the main agent's permission
        # state; they also inherit policy/compactor/usage so they can't loop
        # unbounded or blow past token budgets undetected.
        sub_permissions = PermissionManager(mode=Mode.AUTO)
        return Agent(
            provider,
            default_tools(
                todo_store=todo_store,
                permissions=sub_permissions,
                memory_store=memory_store,
                skill_loader=skill_loader,
                task_store=task_store,
            ),
            sub_permissions,
            config,
            system_prompt,
            todo_store=todo_store,
            compactor=compactor,
            hooks=hooks,
            policy=policy,
            usage=usage,
            memory_store=memory_store,
        )

    hooks = HookManager(config.workdir)
    if flags.is_enabled("dangerous_command_guard"):
        hooks.register("pre_tool_use", dangerous_command_hook)
    loaded_hooks = hooks.load_json()

    tools = default_tools(
        todo_store=todo_store,
        permissions=permissions,
        ask_callback=renderer.ask_question,
        agent_factory=_agent_factory,
        workdir=config.workdir,
        scheduler=scheduler,
        flags=flags,
        usage=usage,
        display_callback=lambda text: renderer.console.print(text, highlight=False),
        iterations_getter=lambda: agent.iterations,
        memory_store=memory_store,
        skill_loader=skill_loader,
        task_store=task_store,
        hooks=hooks,
    )

    if not args.no_mcp:
        from .services.mcp import load_mcp_tools
        added = load_mcp_tools(config.workdir, tools)
        if added:
            renderer.info(f"Loaded {len(added)} MCP tool(s): {', '.join(added)}")

    if flags.is_enabled("lsp"):
        from .services.lsp import load_lsp_tools
        added = load_lsp_tools(config.workdir, tools)
        if added:
            renderer.info(f"Loaded LSP server: {', '.join(added)}")

    if flags.is_enabled("web_browser"):
        if "browser_action" in tools:
            renderer.info("Web browser tool enabled (Playwright).")
        else:
            renderer.info(
                "Web browser tool disabled: install playwright + `playwright install chromium`."
            )

    compactor = Compactor(
        threshold_tokens=config.compact_threshold,
        context_window=effective_context_window(config),
    )
    session_store = SessionStore(config.workdir)

    policy = PolicyLimits.load(config.workdir)
    if loaded_hooks:
        renderer.info(f"Loaded {loaded_hooks} hook(s) from .ohwang/hooks.json.")

    agent = Agent(
        provider,
        tools,
        permissions,
        config,
        system_prompt,
        todo_store=todo_store,
        compactor=compactor,
        hooks=hooks,
        policy=policy,
        usage=usage,
        memory_store=memory_store,
    )

    if flags.is_enabled("proactive") and not args.no_proactive:
        scheduler.start()
        renderer.info("Proactive scheduler running (cron_create/delete/list).")
    else:
        renderer.info("Proactive scheduler disabled.")

    return (
        agent,
        renderer,
        config,
        session_store,
        scheduler,
        memory_extractor,
        skill_loader,
        flags,
        session_summarizer,
    )


def _run_once(
    agent: Agent,
    renderer: Renderer,
    prompt: str,
    run_lock: Lock,
    memory_extractor=None,
) -> None:
    with run_lock:
        try:
            agent.run(
                prompt,
                on_text=renderer.stream_text,
                on_tool_call=renderer.tool_call,
                on_tool_result=renderer.tool_result,
                on_compact=lambda b, a: renderer.warn(
                    f"Context compacted: {b} -> {a} messages."
                ),
            )
        except Exception as exc:
            renderer.warn(f"Error: {exc}")
    renderer.end_turn()
    if memory_extractor is not None and agent.messages:
        try:
            added = memory_extractor.maybe_extract(agent.provider, agent.messages)
            if added:
                renderer.info(f"Auto-saved {added} memory fact(s).")
        except Exception:
            pass


def _suggest_prompts(workdir: str, agent: Agent) -> list[str]:
    """Rule-based prompt suggestions for a fresh session (no extra API calls)."""
    suggestions: list[str] = []
    wd = os.path.abspath(workdir)
    try:
        md_files = [
            f for f in os.listdir(wd)
            if f.lower().endswith((".md", ".txt", ".csv")) and os.path.isfile(os.path.join(wd, f))
        ]
    except OSError:
        md_files = []

    if agent.todo_store is not None and agent.todo_store.todos:
        suggestions.append("更新待办进度或查看当前任务清单")
    if md_files:
        names = "、".join(md_files[:3])
        suggestions.append(f"总结或整理现有资料（如 {names}）")
    if agent.memory_store is not None:
        try:
            facts = agent.memory_store.list_facts()
            if facts:
                suggestions.append("回顾项目记忆中的关键决策")
        except Exception:
            pass
    if agent.iterations > 0:
        suggestions.append("继续上一轮未完成的工作")
    if len(suggestions) < 2:
        suggestions.append("告诉我今天要完成什么工作")
    return suggestions[:3]


def _cmd_resume(agent, renderer, session_store):
    items = session_store.list()
    if not items:
        renderer.info("No saved sessions.")
        return
    for i, it in enumerate(items, 1):
        renderer.info(f"  [{i}] {it['id']}  ({it['n_messages']} msgs) {it['preview'][:40]}")
    choice = renderer.console.input("Pick session number (blank to cancel): ").strip()
    if not choice:
        return
    try:
        sid = items[int(choice) - 1]["id"]
    except (ValueError, IndexError):
        renderer.warn("Invalid choice.")
        return
    data = session_store.load_full(sid)
    if data is None:
        renderer.warn("Failed to load session.")
        return
    agent.messages = data.get("messages", [])
    agent.session_summary = data.get("summary", "") or ""
    agent._invalidate_system()
    renderer.info(f"Resumed session {sid} ({len(agent.messages)} messages).")


def _cmd_save(agent, renderer, session_store, session_summarizer=None):
    if not agent.messages:
        renderer.info("Nothing to save (empty conversation).")
        return
    preview = ""
    for m in agent.messages:
        if m["role"] == "user":
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if b.get("type") == "text":
                        preview = b["text"][:80]
                        break
            break
    summary = ""
    if session_summarizer is not None:
        try:
            summary = session_summarizer.summarize(agent.provider, agent.messages)
        except Exception:
            summary = ""
        if not summary:
            renderer.warn("Session summary generation failed; saving without summary.")
    sid = session_store.save(agent.messages, preview, summary)
    renderer.info(f"Saved session {sid} ({len(agent.messages)} messages).")


def _cmd_cost(agent, renderer, config):
    try:
        tok = agent.provider.usage_report()
    except Exception:
        tok = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
    cost = calculate_cost(
        tok["prompt_tokens"],
        tok["completion_tokens"],
        config.provider,
        agent.provider.model,
    )
    renderer.info(f"Cost: {format_cost(cost)}")
    renderer.info(
        f"Tokens: {tok['prompt_tokens']} in / {tok['completion_tokens']} out "
        f"({tok['calls']} calls)"
    )
    if cost is None:
        renderer.warn(
            f"No price for {config.provider}/{agent.provider.model} in price table."
        )


def repl(
    agent: Agent,
    renderer: Renderer,
    config: Config,
    session_store: SessionStore,
    scheduler: Scheduler,
    flags: FeatureFlags,
    run_lock: Lock,
    one_shot: str | None,
    memory_extractor=None,
    skill_loader=None,
    session_summarizer=None,
) -> None:
    renderer.info(f"OhWangAgent — provider={config.provider} model={config.model} mode={agent.permissions.mode.label}")
    renderer.info("Type /help for commands, /exit to quit.")

    if one_shot:
        _run_once(agent, renderer, one_shot, run_lock, memory_extractor)
        return

    if agent.hooks is not None:
        agent.hooks.emit("session_start")

    if not agent.messages:
        suggestions = _suggest_prompts(config.workdir, agent)
        if suggestions:
            renderer.info("Maybe start with:")
            for s in suggestions:
                renderer.info(f"  • {s}")

    while True:
        try:
            line = read_stdin_line("\nohwang> ")
        except (EOFError, KeyboardInterrupt):
            renderer.info("\nBye.")
            break
        line = line.strip()
        if not line:
            continue
        if line in ("/exit", "/quit"):
            break
        if line == "/clear":
            agent.reset()
            renderer.info("Conversation cleared.")
            continue
        if line == "/tools":
            for t in agent.tools:
                renderer.info(f"  {t.name}  [{t.default_permission}]")
            continue
        if line == "/flags":
            for name, enabled in sorted(flags.list_all().items()):
                renderer.info(f"  {name}: {'on' if enabled else 'off'}")
            continue
        if line == "/cron":
            if not scheduler.count():
                renderer.info("No cron jobs.")
            else:
                for job in scheduler.list():
                    renderer.info(f"  {job.id}  {job.expression}  {job.prompt[:60]}")
            continue
        if line.startswith("/cron "):
            parts = shlex.split(line[len("/cron "):])
            if len(parts) != 3:
                renderer.info("Usage: /cron <id> '<cron expr>' '<prompt>'")
                continue
            job_id, expr, prompt = parts
            ok = scheduler.add(job_id, expr, prompt)
            renderer.warn(f"Cron job {job_id} scheduled." if ok else f"Failed to add {job_id}.")
            continue
        if line == "/worktree":
            from .services.worktree import WorktreeManager
            renderer.info(WorktreeManager(config.workdir).list() or "(none)")
            continue
        if line == "/summary":
            renderer.info(agent.usage.report() if agent.usage else "Usage tracking off.")
            renderer.info(f"Iterations: {agent.iterations}  Messages: {len(agent.messages)}")
            try:
                tok = agent.provider.usage_report()
                renderer.info(
                    f"Tokens: {tok['total_tokens']} total "
                    f"({tok['prompt_tokens']} in / {tok['completion_tokens']} out, "
                    f"{tok['calls']} calls)"
                )
            except Exception:
                pass
            continue
        if line == "/cost":
            _cmd_cost(agent, renderer, config)
            continue
        if line == "/skills":
            if skill_loader is None:
                renderer.info("Skills disabled (feature flag 'skill' is off).")
            else:
                names = skill_loader.list_names() or []
                if not names:
                    renderer.info("No skills available.")
                else:
                    renderer.info("Available skills: " + ", ".join(sorted(names)))
            continue
        if line == "/help":
            renderer.info(
                "Commands: /help /tools /flags /skills /cron [/cron <id> '<expr>' '<prompt>'] "
                "/worktree /summary /cost /clear /auto /mode /model <id> /todo /save /resume /exit"
            )
            continue
        if line == "/auto":
            agent.permissions.auto_approve = not agent.permissions.auto_approve
            renderer.warn(f"Auto-approve {'ON' if agent.permissions.auto_approve else 'OFF'}.")
            continue
        if line == "/mode":
            renderer.info(f"Current mode: {agent.permissions.mode.label}")
            continue
        if line == "/todo":
            rendered = agent.todo_store.render() if agent.todo_store else ""
            renderer.info(rendered.strip() or "No todos.")
            continue
        if line == "/save":
            _cmd_save(agent, renderer, session_store, session_summarizer)
            continue
        if line == "/resume":
            _cmd_resume(agent, renderer, session_store)
            continue
        if line.startswith("/model "):
            new_model = line[len("/model "):].strip()
            config.model = new_model
            agent.provider.model = new_model
            renderer.info(f"Model set to {new_model}.")
            continue
        _run_once(agent, renderer, line, run_lock, memory_extractor)

    if agent.hooks is not None:
        agent.hooks.emit("session_end")


def main(argv=None) -> int:
    setup_utf8()
    args = parse_args(argv)
    _prepare_workdir(args)
    _warn_noninteractive_approval(args)
    _load_env(os.getcwd())
    run_lock = Lock()
    (
        agent,
        renderer,
        config,
        session_store,
        scheduler,
        memory_extractor,
        skill_loader,
        flags,
        session_summarizer,
    ) = build_agent(args, run_lock)
    try:
        repl(
            agent,
            renderer,
            config,
            session_store,
            scheduler,
            flags,
            run_lock,
            one_shot=args.prompt,
            memory_extractor=memory_extractor,
            skill_loader=skill_loader,
            session_summarizer=session_summarizer,
        )
    finally:
        scheduler.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
