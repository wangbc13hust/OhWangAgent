# OhWangAgent

A Claude-Code-style coding agent built in Python. It reproduces the core
architecture of Anthropic's Claude Code: an agentic loop that drives tool
calls, with a pluggable multi-model provider layer.

## Architecture

```
CLI / REPL  ──►  Agent loop  ──►  Provider (Anthropic | OpenAI-compatible)
                      │
                      ▼
                 Tool registry
   (bash, file_read, file_write, file_edit, grep, glob)
                      │
                      ▼
               Permission manager  ──►  ask / allow / always
```

- **`ohwang/agent.py`** — the loop: LLM → parse tool_use → run tool → feed
  result back → repeat until the model stops calling tools.
- **`ohwang/providers/`** — `BaseProvider` emits unified streaming events
  (`text` / `tool_use` / `stop`). `AnthropicProvider` passes through; the
  `OpenAIProvider` converts to/from OpenAI function-calling, so any
  OpenAI-compatible endpoint works (OpenAI, DeepSeek, Kimi, Qwen, local…).
- **`ohwang/tools/`** — each tool is a `BaseTool` subclass with a JSON schema,
  a default permission, and an `execute()` method. Add a tool by dropping in a
  class and registering it.
- **`ohwang/permissions.py`** — every tool call is checked: read-only tools
  auto-allow; mutating tools ask (y/n/always) unless `--auto-approve`.
- **`ohwang/tui/render.py`** — Rich-based streaming output.

## Install

```powershell
cd D:\ai-project\OhWangAgent
.venv\Scripts\Activate.ps1
pip install -e .
```

## Configure

Set an API key (choose your provider):

```powershell
# Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# or OpenAI-compatible
$env:OPENAI_API_KEY = "sk-..."
```

## Run

```powershell
# interactive REPL (default provider: anthropic)
ohwang

# one-shot
ohwang "read pyproject.toml and summarize it"

# OpenAI-compatible provider + custom model + auto-approve
ohwang --provider openai --base-url https://api.deepseek.com --model deepseek-chat -y

# switch provider/model/model inside the REPL
ohwang> /model claude-sonnet-4-5-20250929
ohwang> /auto
ohwang> /tools
ohwang> /clear
ohwang> /exit
```

## Roadmap (toward a full Claude Code clone)

This MVP covers the core loop + tools + multi-model providers. Remaining
phases:

- [ ] Context compaction when history grows long
- [ ] Session history / `/resume`
- [ ] Sub-agent tool (`AgentTool`) for parallel delegation
- [ ] MCP client support
- [ ] Skill / plugin system
- [ ] Full TUI (Textual)

## Status

Educational project inspired by the publicly exposed Claude Code architecture.
Not affiliated with Anthropic.
