# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

OhWangAgent — an interactive CLI **office agent** in Python (v0.3.0): documents, meeting
notes, research, task lists, and code editing, driven by an agentic loop with a pluggable
multi-provider layer (Anthropic + OpenAI-compatible endpoints). It mirrors Claude Code's
architecture: Agent loop + tool registry + permissions/hooks/policy/memory/scheduler.

> **Read these first:** `AGENTS.md` (mandatory dev workflow), `docs/ARCHITECTURE.md`
> (detailed module map, data flows, gotchas), `docs/CHANGELOG.md` (daily progress).
> Windows 11 / Git Bash; venv at `.venv`.

## Commands

```bash
# Run the full test suite (559 tests) — must be green before committing
$env:PYTHONPATH="D:\ai-project\OhWangAgent"; .venv\Scripts\python.exe -m pytest -q

# Single test file / single test
.venv\Scripts\python.exe -m pytest tests/test_flags.py -q
.venv\Scripts\python.exe -m pytest tests/test_flags.py -q -k "env_truthy"

# Install (editable)
.venv\Scripts\Activate.ps1
pip install -e .

# Run the app (interactive REPL / one-shot task)
ohwang --provider deepseek
ohwang --provider deepseek "把今天的周会内容写成一份会议纪要"

# Coverage (current ~91%)
coverage run --source=ohwang -m pytest
coverage report --omit="ohwang/tui/widgets/*"
```

- No lint/type-check gate — passing tests is the bar (see `AGENTS.md`).
- `pyproject.toml` sets `pythonpath = ["."]`, so tests also run from a bare
  `.venv\Scripts\python.exe -m pytest`; the `PYTHONPATH=` form above is the documented one.
- Providers & default models live in `ohwang/config.py::PROVIDER_PRESETS`
  (env var, default model, base_url, context window per provider).
- CLI flags: `--provider`, `--model`, `--api-key`, `--base-url`, `--max-tokens`,
  `-y/--auto-approve`, `--plan`, `--compact-threshold`, `--context-window`,
  `--workdir`, `--no-mcp`, `--no-proactive`, positional `prompt` for one-shot.

## Architecture

```
CLI/REPL (cli.py) → Agent loop (agent.py) → Provider (providers/) → Tool registry (tools/)
                        │                          │
                        ▼                          ▼
                  services/ (cross-cutting)   PermissionManager (modes.py, permissions.py)
```

**Agent loop** (`ohwang/agent.py`) — `Agent.run()`: append user msg → `microcompact()`
truncates oversized (>30K char) tool results → `Compactor` summarizes history when a
window-derived threshold is hit (circuit-breaker: 3 consecutive failures → hard snip) →
`provider.chat()` emits a unified event stream (`text` / `tool_use`); if the API throws a
"prompt too long" error, compact once and retry same turn. Tool calls go through
`_run_tool()`: **hook(pre) → permission → policy → execute → usage/post-hook**. Tool
exceptions become `is_error` result blocks, never crash the loop.

**Provider layer** (`ohwang/providers/`) — `BaseProvider.chat()` is the only interface;
it streams `{"type": "text"|"tool_use", ...}` and accumulates usage counters.
`AnthropicProvider` passes the native tool_use protocol through (prompt caching on by
default, disable with `DISABLE_PROMPT_CACHING=1`). `OpenAIProvider` converts tool_use ↔
OpenAI function-calling, so **any OpenAI-compatible endpoint works** (DeepSeek, Kimi,
Qwen, Zhipu, local). 6 presets in `config.py`.

**Tool layer** (`ohwang/tools/`) — each tool is a `BaseTool` subclass declaring `name`,
`description`, `input_schema`, `default_permission`, and `execute()`. Register in
`default_tools(...)` in `tools/__init__.py`; dependency-gated tools (todo, task, memory,
skill, plan_mode, ask_user, agent, worktree, cron, browser, web_search) register only when
their dependency is passed in (~39 tools). `bash`/`powershell` share one execution path in
`tools/shell_output.py` (`stream_command` for real-time output, `command_result` for the
final block); optional `output_callback` gives live TTY feedback.

**Services** (`ohwang/services/`) — cross-cutting, mostly leaf modules (only
`summarizer → compact → tokens` imports internally). Key ones: `window`/`compact`
(context window + compaction), `tokens` (tiktoken exact / heuristic fallback), `memory`
(MemoryStore + MemoryExtractor, layered project/global), `hooks` (9 lifecycle events),
`guards` (dangerous shell command blocking), `policy` (call limits), `cost` (`/cost`
estimate), `scheduler` (cron, persisted), `git_context` (injects branch/commits/dirty
state into the system prompt), plus session/search/mcp/worktree/browser/lsp/settings/summary.

**Permissions** (`ohwang/permissions.py`, `modes.py`) — 4 modes: DEFAULT (per-tool
permission + ask), PLAN (read-only), AUTO (allow all), BYPASS (skip). `.ohwang/settings.json`
holds `allow`/`ask`/`deny` glob lists; precedence **deny > allow > ask > tool default**, and
deny beats "always" memory. `exit_plan_mode` requires user approval (non-interactive stdin
defaults to deny — the model cannot exit read-protection by itself).

**Feature flags** (`ohwang/flags.py`) — three-level override:
`OHWANG_FEATURE_<NAME>` env → `.ohwang/flags.json` → built-in defaults. Env truthiness is
case-insensitive (`TRUE`/`True`/`YES` all true).

**Data dir** — runtime state lives under `.ohwang/` in the workdir: `settings.json`,
`policy.json`, `hooks.json`, `flags.json`, `cron.json`, `lsp.json`, `memory/facts.json`,
`sessions/*.json`, `tasks/*.json`, `snips/*.txt`, `skills/`, `mcp.json`.

**Tests** (`tests/`, 559 cases, 91% coverage) — `helpers.py` provides `ScriptedProvider`
(recorded event replay), `MockSearchProvider`, and `build_agent()` so integration tests run
with no network or real model. MCP is tested with a real stdio fake server; Playwright and
LSP are mocked/stubbed. Office-workflow scenarios live in `test_scenarios.py`.

## Extension points

- **Add a tool**: new `BaseTool` subclass in `ohwang/tools/`, register in `default_tools()`.
- **Add a model**: new entry in `PROVIDER_PRESETS`; OpenAI-compatible → zero code, else
  implement `BaseProvider`.
- **Add a service**: new module in `ohwang/services/`, export from `__init__.py`, wire in
  `cli.build_agent()`.
- **Add a flag**: new key in `flags.py::_DEFAULTS`, gate with `flags.is_enabled()`.

## Gotchas

- **File writes**: chunk large writes — Write the body, then Edit to append in pieces, then
  Read back to confirm integrity (single large writes can fail).
- **Assembly order is hardened**: `cli.build_agent()` builds `hooks`/`compactor`/`policy`
  before the closures that use them and wires `_run_locked` + `scheduler._runner` only after
  `agent = Agent(...)`; the `tools↔agent` cycle (BriefTool needs `agent.iterations`) is broken
  by an explicit `agent_ref` box. `scheduler.start()` runs only after the agent is fully
  assembled, and a single `run_lock` is shared between REPL and cron to prevent concurrent
  `run()` corruption.
- Sub-agents get an independent AUTO `PermissionManager` but inherit the main agent's
  policy/compactor/usage/hooks; provider token accounting is shared by design.
- TTY-only feedback (shell streaming, sub-agent progress lines, per-turn indicators) is
  gated on `sys.stdout.isatty()` so pipelines/CI stay quiet.
- `web_browser` requires Playwright; `web_search`/`web_fetch` fall back without it. Search
  order is Tavily → Bing (default, China-reachable) → DuckDuckGo.
