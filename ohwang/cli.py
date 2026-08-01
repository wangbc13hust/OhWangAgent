from __future__ import annotations

import argparse
import os
import sys
from threading import Lock

from .agent import Agent
from .config import PROVIDER_PRESETS, Config
from .flags import FeatureFlags
from .modes import Mode
from .permissions import PermissionManager
from .prompts import build_system_prompt
from .providers import create_provider
from .services import Compactor, SessionStore
from .services.scheduler import Scheduler
from .services.settings import load_settings
from .tools import default_tools
from .tools.todo import TodoStore
from .tui import Renderer


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
        default=100_000,
        help="Token estimate threshold to trigger context compaction",
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


def build_agent(args: argparse.Namespace):
    config = Config(
        provider=args.provider,
        model=args.model or "",
        api_key=args.api_key or "",
        max_tokens=args.max_tokens,
        auto_approve=args.auto_approve,
        plan=args.plan,
        compact_threshold=args.compact_threshold,
        workdir=args.workdir or os.getcwd(),
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

    system_prompt = build_system_prompt(config.workdir)

    run_lock = Lock()
    scheduler = Scheduler(runner=None)

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
        return Agent(
            provider,
            default_tools(todo_store=todo_store, permissions=permissions),
            PermissionManager(mode=Mode.AUTO),
            config,
            system_prompt,
        )

    tools = default_tools(
        todo_store=todo_store,
        permissions=permissions,
        ask_callback=renderer.ask_question,
        agent_factory=_agent_factory,
        workdir=config.workdir,
        scheduler=scheduler,
        flags=flags,
    )

    if not args.no_mcp:
        from .services.mcp import load_mcp_tools
        added = load_mcp_tools(config.workdir, tools)
        if added:
            renderer.info(f"Loaded {len(added)} MCP tool(s): {', '.join(added)}")

    if flags.is_enabled("proactive") and not args.no_proactive:
        scheduler.start()
        renderer.info("Proactive scheduler running (cron_create/delete/list).")
    else:
        renderer.info("Proactive scheduler disabled.")

    if flags.is_enabled("web_browser"):
        if "browser_action" in tools:
            renderer.info("Web browser tool enabled (Playwright).")
        else:
            renderer.info(
                "Web browser tool disabled: install playwright + `playwright install chromium`."
            )

    compactor = Compactor(threshold_tokens=config.compact_threshold)
    session_store = SessionStore(config.workdir)

    agent = Agent(
        provider,
        tools,
        permissions,
        config,
        system_prompt,
        todo_store=todo_store,
        compactor=compactor,
    )
    return agent, renderer, config, session_store, scheduler


def _run_once(agent: Agent, renderer: Renderer, prompt: str, run_lock: Lock) -> None:
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
    msgs = session_store.load(sid)
    if msgs is None:
        renderer.warn("Failed to load session.")
        return
    agent.messages = msgs
    renderer.info(f"Resumed session {sid} ({len(msgs)} messages).")


def _cmd_save(agent, renderer, session_store):
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
    sid = session_store.save(agent.messages, preview)
    renderer.info(f"Saved session {sid} ({len(agent.messages)} messages).")


def repl(
    agent: Agent,
    renderer: Renderer,
    config: Config,
    session_store: SessionStore,
    scheduler: Scheduler,
    flags: FeatureFlags,
    run_lock: Lock,
    one_shot: str | None,
) -> None:
    renderer.info(f"OhWangAgent — provider={config.provider} model={config.model} mode={agent.permissions.mode.label}")
    renderer.info("Type /help for commands, /exit to quit.")

    if one_shot:
        _run_once(agent, renderer, one_shot, run_lock)
        return

    while True:
        try:
            line = input("\nohwang> ")
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
            parts = line[len("/cron "):].split(maxsplit=2)
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
        if line == "/help":
            renderer.info(
                "Commands: /help /tools /flags /cron [/cron <id> '<expr>' '<prompt>'] "
                "/worktree /clear /auto /mode /model <id> /todo /save /resume /exit"
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
            _cmd_save(agent, renderer, session_store)
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
        _run_once(agent, renderer, line, run_lock)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.workdir:
        os.chdir(args.workdir)
    agent, renderer, config, session_store, scheduler = build_agent(args)
    flags = FeatureFlags(config.workdir)
    run_lock = Lock()
    try:
        repl(agent, renderer, config, session_store, scheduler, flags, run_lock, one_shot=args.prompt)
    finally:
        scheduler.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
