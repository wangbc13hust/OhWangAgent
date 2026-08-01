# OhWangAgent

An interactive CLI **office agent** built in Python: write and organize
documents, take meeting notes, extract and summarize information, search files
and the web, manage task lists, and edit code — all driven by an agentic loop
with a pluggable multi-model provider layer.

## Architecture

```
CLI / REPL  ──►  Agent loop  ──►  Provider (Anthropic | OpenAI-compatible)
                      │
                      ▼
                 Tool registry
   (bash, powershell, file_*, grep, glob, web_*, todo, cron, worktree, ...)
                      │
                      ▼
               Permission manager  ──►  ask / allow / always
```

详细设计见 **`docs/ARCHITECTURE.md`**（模块图、Agent 循环、权限/钩子/策略/
记忆/调度机制、扩展点、数据目录、已知缺口）。每日进度见 **`docs/CHANGELOG.md`**。

- **`ohwang/agent.py`** — the loop: LLM → parse tool_use → run tool → feed
  result back → repeat until the model stops calling tools.
- **`ohwang/providers/`** — `BaseProvider` emits unified streaming events
  (`text` / `tool_use`). The `OpenAIProvider` converts to/from OpenAI
  function-calling, so any OpenAI-compatible endpoint works (DeepSeek, Kimi,
  Qwen, local…); `AnthropicProvider` passes through.
- **`ohwang/tools/`** — each tool is a `BaseTool` subclass with a JSON schema,
  a default permission, and an `execute()` method. Add a tool by dropping in a
  class and registering it.
- **`ohwang/permissions.py`** — every tool call is checked: read-only tools
  auto-allow; mutating tools ask (y/n/always) unless `--auto-approve`.
  `.ohwang/settings.json` can set `allow` / `ask` / `deny` glob rules.
- **`ohwang/services/`** — compact, session, settings, search, mcp, worktree,
  scheduler, browser, memory, hooks, policy, summary.
- **`ohwang/tui/render.py`** — Rich-based streaming output (UTF-8 safe).

## Install

```powershell
cd D:\ai-project\OhWangAgent
.venv\Scripts\Activate.ps1
pip install -e .
```

## Configure

Set an API key for your provider:

```powershell
# DeepSeek (default for office work)
$env:DEEPSEEK_API_KEY = "sk-..."

# Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# OpenAI / Kimi / Qwen / Zhipu…
$env:OPENAI_API_KEY = "sk-..."   # + --base-url
```

Providers and default models are defined in `ohwang/config.py`
(`deepseek-v4-flash`, `glm-5.2`, `claude-sonnet-4-5-20250929`, …).

## Run

```powershell
# interactive REPL
ohwang --provider deepseek

# one-shot office task
ohwang --provider deepseek "把今天的周会内容写成一份会议纪要"

# auto-approve tool calls + plan mode
ohwang --provider deepseek -y --plan

# switch provider/model inside the REPL
ohwang> /model deepseek-v4-pro
ohwang> /auto
ohwang> /tools
ohwang> /cron
ohwang> /flags
ohwang> /save
ohwang> /exit
```

## Features

- **Office workflows** — documents, meeting notes, reports, data extraction,
  web research, todo-driven multi-step tasks (see `tests/test_scenarios.py`).
- **Tools** — bash, powershell, file_read/write/edit, grep, glob,
  web_fetch, web_search, todo_write, plan mode, ask_user, sub-agent,
  cron scheduling, git worktree, MCP client, browser (Playwright).
- **Context compaction**, session save/resume, `.ohwang/settings.json`
  permission rules, feature flags, skills/plugins/LSP/memory.
- **222 unit tests + office scenario tests** (`tests/`).

## Status

Educational project. Not affiliated with Anthropic.
