from __future__ import annotations

import argparse
import os
import sys

from .agent import Agent
from .config import PROVIDER_PRESETS, Config
from .permissions import PermissionManager
from .prompts import SYSTEM_PROMPT
from .providers import create_provider
from .tools import default_tools
from .tui import Renderer


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ohwang",
        description="OhWangAgent — a Claude-Code-style coding agent.",
    )
    p.add_argument("--provider", choices=list(PROVIDER_PRESETS), default="anthropic")
    p.add_argument("--model", default=None, help="Model id (overrides preset)")
    p.add_argument("--api-key", default=None, help="API key (else read from env)")
    p.add_argument(
        "--base-url", default=None, help="OpenAI-compatible endpoint (openai provider)"
    )
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument(
        "-y",
        "--auto-approve",
        action="store_true",
        help="Auto-approve every tool call (no prompts)",
    )
    p.add_argument("--workdir", default=None, help="Working directory")
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
        workdir=args.workdir or os.getcwd(),
    ).resolve()

    if not config.api_key:
        env_var = PROVIDER_PRESETS.get(config.provider, {}).get("env", "")
        sys.stderr.write(f"Error: no API key. Set ${env_var} or pass --api-key.\n")
        sys.exit(2)

    provider = create_provider(config, base_url=args.base_url)
    tools = default_tools()
    renderer = Renderer()

    ask_callback = None if config.auto_approve else renderer.ask
    permissions = PermissionManager(
        auto_approve=config.auto_approve, ask_callback=ask_callback
    )
    agent = Agent(provider, tools, permissions, config, SYSTEM_PROMPT)
    return agent, renderer, config


def _run_once(agent: Agent, renderer: Renderer, prompt: str) -> None:
    try:
        agent.run(
            prompt,
            on_text=renderer.stream_text,
            on_tool_call=renderer.tool_call,
            on_tool_result=renderer.tool_result,
        )
    except Exception as exc:
        renderer.warn(f"Error: {exc}")
    renderer.end_turn()


def repl(agent: Agent, renderer: Renderer, config: Config, one_shot: str | None) -> None:
    renderer.info(f"OhWangAgent — provider={config.provider} model={config.model}")
    if config.auto_approve:
        renderer.warn("Auto-approve ON — tools run without asking.")
    renderer.info("Type /help for commands, /exit to quit.")

    if one_shot:
        _run_once(agent, renderer, one_shot)
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
        if line == "/help":
            renderer.info("Commands: /help /tools /clear /auto /model <id> /exit")
            continue
        if line == "/auto":
            config.auto_approve = not config.auto_approve
            agent.permissions.auto_approve = config.auto_approve
            renderer.warn(f"Auto-approve {'ON' if config.auto_approve else 'OFF'}.")
            continue
        if line.startswith("/model "):
            new_model = line[len("/model ") :].strip()
            config.model = new_model
            agent.provider.model = new_model
            renderer.info(f"Model set to {new_model}.")
            continue
        _run_once(agent, renderer, line)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.workdir:
        os.chdir(args.workdir)
    agent, renderer, config = build_agent(args)
    repl(agent, renderer, config, one_shot=args.prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
