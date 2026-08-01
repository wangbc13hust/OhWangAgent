# OhWangAgent 架构文档

> 版本：v0.3.0 · 对应代码提交 `f0a24af` · 450 测试全绿（覆盖率 98%）
>
> 定位：交互式 CLI **办公 agent** —— 文档撰写、会议纪要、资料检索、任务管理、
> 报告生成 + 软件工程能力。架构对齐 Claude Code（Agent 循环 + 工具注册表 +
> 权限/钩子/策略/记忆/调度机制），Provider 层可插拔，覆盖 6 家模型。

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  ohwang/cli.py        REPL + 一次性任务 + /命令 + cron + 记忆提取   │
│  ohwang/tui/render.py Rich 流式渲染（UTF-8 控制台）                │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/agent.py      Agent 循环：LLM → tool_use → 执行 → 回灌      │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/providers/    统一事件流（text / tool_use）                │
│    base.py → anthropic_provider → openai_provider(6 家兼容)       │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/tools/        BaseTool 注册表（约 31 个工具，按依赖启停）     │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/services/     横切服务：记忆/钩子/策略/调度/会话/压缩/…      │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/permissions.py 权限四模式 + .ohwang/settings.json 规则      │
│  ohwang/flags.py      Feature flag 三级覆盖                        │
│  ohwang/config.py     Provider 预设与运行配置                       │
└─────────────────────────────────────────────────────────────────┘
```

一次交互的数据流：

```
用户输入
  │
  ▼
cli.main() ── build_agent() 装配 Agent/渲染器/服务
  │
  ▼
agent.run(prompt)
  │  ① 追加 user 消息 → ② 需要时上下文压缩
  │  ③ provider.chat() 产出事件流（text / tool_use）
  │  ④ 收集 tool_use → 逐条 _run_tool()
  │        ├─ hooks.run_pre_tool   （可阻断/改写输入）
  │        ├─ permissions.can_run  （模式 + 规则）
  │        ├─ policy.check_tool    （调用上限）
  │        ├─ tool.execute(input)  （执行）
  │        └─ usage.record / hooks.run_post_tool
  │  ⑤ tool_result 回灌为 user 消息 → 循环直到无 tool_use
  ▼
最终文本 → renderer 流式输出
  ▼
cli._run_once() 收尾 → MemoryExtractor.maybe_extract() 自动记忆
```

---

## 2. 目录结构

```
ohwang/
├── cli.py                 入口：参数解析、装配、REPL、/命令、一次性任务
├── __main__.py            python -m ohwang 入口
├── agent.py               Agent 循环核心
├── config.py              PROVIDER_PRESETS + Config 数据类
├── flags.py               FeatureFlags（env + .ohwang/flags.json + 默认）
├── modes.py               Mode 枚举（default/plan/auto/bypass）
├── permissions.py         PermissionManager 权限决策
├── prompts.py             System prompt 构建
│
├── providers/             模型层
│   ├── base.py            BaseProvider（事件流协议：text/tool_use）
│   ├── anthropic_provider.py  Anthropic 原生直连
│   └── openai_provider.py     OpenAI 函数调用兼容（zhipu/deepseek/kimi/qwen/openai…）
│
├── tools/                 工具层（BaseTool 子类）
│   ├── base.py            BaseTool / ToolResult
│   ├── registry.py        ToolRegistry（name → tool）
│   ├── __init__.py        default_tools() 按依赖装配
│   ├── bash.py / powershell.py       Shell 执行（共用 shell_output.py）
│   ├── shell_output.py               truncate / command_result 公共 helper
│   ├── file_read.py / file_write.py / file_edit.py / grep.py / glob.py
│   ├── web_fetch.py / web_search.py / web_browser.py   Web
│   ├── tool_search.py     工具检索（把 registry 作为工具暴露）
│   ├── todo.py            TodoWriteTool + TodoStore
│   ├── plan_mode.py       enter/exit_plan_mode
│   ├── ask_user.py        ask_user_question
│   ├── agent_tool.py      子 agent（agent_factory）
│   ├── schedule.py        cron_create/delete/list
│   ├── worktree.py        enter/exit_worktree
│   ├── config.py          config（运行时权限规则）
│   ├── sleep.py / synthetic_output.py / brief.py / snip.py   P3-C 输出类
│   ├── memory.py          memory_read/write（经 default_tools(memory_store=...) 注册）
│   └── lsp_diagnose.py    lsp_diagnose（经 load_lsp_tools() 注册，读取 .ohwang/lsp.json）
│
├── services/             横切服务
│   ├── compact.py         上下文压缩（token 阈值）
│   ├── tokens.py          token 估算
│   ├── session.py         会话保存/resume（.ohwang/sessions/）
│   ├── settings.py        权限规则文件读写
│   ├── search.py          Bing / DuckDuckGo / Tavily 搜索（可回退）
│   ├── mcp.py             MCP 客户端 + 工具封装
│   ├── worktree.py        git worktree 管理
│   ├── scheduler.py       cron 调度器（proactive 模式）
│   ├── browser.py         Playwright 浏览器会话
│   ├── memory.py          MemoryStore + MemoryExtractor（自动记忆提取）
│   ├── hooks.py           HookManager（pre/post/notif）
│   ├── policy.py          PolicyLimits（调用上限）
│   └── summary.py         UsageTracker（工具调用统计）
│
├── skills/               Skill 加载器（.ohwang/skills/，SKILL.md 目录格式 + JSON 兼容）
├── plugins/              Plugin 加载器（.ohwang/plugins/）
└── tui/
    ├── render.py         Renderer（Rich）+ setup_utf8（Windows 控制台编码）
    └── widgets/app.py    Textual TUI（实验性）
```

---

## 3. 核心组件详解

### 3.1 Agent 循环（`ohwang/agent.py`）

`Agent.run(user_input, on_text, on_tool_call, on_tool_result, on_compact)`：

1. 追加 `user` 消息。
2. 达到 `compact_threshold` 时用 `Compactor` 压缩历史。
3. `provider.chat(system, messages, tools, max_tokens)` 产出事件流：
   - `text` → 追加到正文并流式渲染；
   - `tool_use` → 收集。
4. 有 `tool_use` 则每条经 `_run_tool()` 执行（见下），结果组装为一条
   `user` 消息回灌；无 `tool_use` 即结束。
5. `_run_tool()` 调用链：**hook(pre) → 权限 → policy → 执行 → 统计/后置钩子**。

状态：`agent.messages`（会话历史）、`agent.iterations`、`agent.usage`。

### 3.2 Provider 层（`ohwang/providers/`）

- `BaseProvider.chat(...)` 是唯一抽象接口，产出统一事件流字典
  `{"type": "text"|"tool_use", ...}`。
- `AnthropicProvider`：Anthropic 原生 tool_use 协议直通。
- `OpenAIProvider`：把 tool_use 事件 ↔ OpenAI function-calling 转换，
  因此任何 OpenAI 兼容端点（DeepSeek/Kimi/Qwen/智谱/本地模型）都可直接接入。
- 6 家预设见 `config.py::PROVIDER_PRESETS`（env 变量、默认模型、base_url）。

### 3.3 工具层（`ohwang/tools/`）

每个工具是 `BaseTool` 子类，声明四要素：

| 属性 | 含义 |
| :--- | :--- |
| `name` | 工具名（发给模型） |
| `description` | 使用说明 |
| `input_schema` | JSON Schema |
| `default_permission` | `allow` / `ask` / `deny` 缺省权限 |

`default_tools(...)` 按依赖装配注册表：核心工具无条件注册，扩展工具
（todo / plan_mode / ask_user / agent / cron / browser / web_search）
仅在传入对应依赖时注册。`ToolSearchTool` 把注册表本身暴露为可搜索工具。

### 3.4 权限系统（`ohwang/permissions.py` + `modes.py`）

- 四种模式：`DEFAULT`（按 default_permission + ask 回调）、`PLAN`（只读，
  仅 `allow` 工具通过）、`AUTO`（全部放行）、`BYPASS`（完全跳过）。
- 规则（`.ohwang/settings.json`）：`allow/ask/deny` 三列表，支持 glob
  （如 `mcp__*`），优先级 deny > allow > ask > 工具默认。
- `always` 记忆：用户对某调用回答 "always" 后，按 `工具名::参数` 签名
  永久放行；退出 PLAN 模式自动还原进入前的模式。

### 3.5 服务层（`ohwang/services/`）

| 服务 | 职责 | 数据 |
| :--- | :--- | :--- |
| `MemoryStore` | 持久记忆 | `CLAUDE.md`/`AGENTS.md` + `.ohwang/memory/facts.json` |
| `MemoryExtractor` | 会话增长 ≥10 条时让模型提炼事实自动入库 | — |
| `HookManager` | pre/post tool + notif 生命周期钩子 | `.ohwang/hooks.json` 命令钩子 |
| `PolicyLimits` | 工具调用总量/单工具上限，防失控循环 | `.ohwang/policy.json` |
| `UsageTracker` | 工具调用统计（`/summary`、brief 工具） | 内存 |
| `Compactor` | 超阈值上下文压缩 | — |
| `SessionStore` | 会话保存/resume | `.ohwang/sessions/*.json` |
| `Scheduler` | cron 调度，agent 空闲时可后台执行任务 | — |
| `MCPClient` | 外部 MCP 服务器工具 | `.ohwang/mcp.json` |
| `SearchProvider` | Tavily(有key) → Bing(默认,国内可达) → DDG 回退；不可达抛 `SearchError` | — |
| `WorktreeManager` | git worktree | — |
| `BrowserSession` | Playwright 浏览器 | — |

### 3.6 配置与开关

- `config.py::Config`：provider/model/api_key/max_tokens/工作目录等，`resolve()`
  用环境变量补齐。
- `flags.py::FeatureFlags`：三级覆盖 `OHWANG_FEATURE_<NAME>` env →
  `.ohwang/flags.json` → 内置默认。控制 web_browser/proactive/memory 等。
- `settings.py`：`.ohwang/settings.json` 权限规则读写（`config` 工具可运行时改）。

### 3.7 渲染与编码（`ohwang/tui/render.py`）

- `Renderer` 基于 Rich：流式文本、工具调用高亮、ask 交互。
- `setup_utf8()`：Windows 下 `SetConsoleOutputCP(65001)` + stdout/stderr
  强制 UTF-8，解决 GBK 控制台中文乱码。

---

## 4. `.ohwang/` 数据目录

| 文件/目录 | 内容 |
| :--- | :--- |
| `settings.json` | 权限规则 allow/ask/deny |
| `policy.json` | 工具调用上限 |
| `hooks.json` | 生命周期命令钩子 |
| `flags.json` | 特性开关覆盖 |
| `memory/facts.json` | 自动/手动记忆事实 |
| `sessions/*.json` | 会话历史 |
| `snips/*.txt` | snip 工具保存的输出片段 |
| `skills/` | Skill 定义：`<name>/SKILL.md`（YAML frontmatter + markdown）或 `<name>.json` |
| `mcp.json` | MCP 服务器列表 |

---

## 5. 扩展点

- **加工具**：在 `ohwang/tools/` 新建 `BaseTool` 子类，并在 `default_tools()`
  中注册（或按依赖条件注册）。
- **加模型**：在 `PROVIDER_PRESETS` 增加预设；若 OpenAI 兼容则零代码接入，
  否则实现 `BaseProvider`。
- **加服务**：在 `ohwang/services/` 新增模块，从 `services/__init__.py` 导出，
  在 `cli.build_agent()` 装配。
- **加特性开关**：`flags.py::_DEFAULTS` 增一项，代码里用 `flags.is_enabled()` 门控。

---

## 6. 测试架构（`tests/`，450 个，覆盖率 98%）

- `helpers.py`：`ScriptedProvider`（重放事件序列）、`MockSearchProvider`、
  `build_agent()`——无网络、无真实模型的集成测试基座。
- 覆盖：工具单元测试、provider 转换、权限/plan 模式、压缩、会话、
  记忆/记忆提取、hooks/policy/usage、调度、worktree、MCP、Skill/Plugin、
  办公场景（`test_scenarios.py`）、P3 新工具（`test_output_tools.py` 等）。
- 覆盖率 98%（`coverage report --omit="ohwang/tui/widgets/*"`）；按模块补齐：
  `test_providers.py`、`test_mcp.py`、`test_browser.py`、`test_lsp.py`、
  `test_hooks.py`、`test_search.py`、`test_plugin.py`、`test_gaps.py`（分支补齐）。
- MCP 用真实 stdio fake server 子进程测 JSON-RPC 握手；Playwright 用 mock
  `playwright` + `playwright.sync_api` 模块。
- 流式：`Renderer.stream_text` 即时输出 + 智能 flush（128字符/50ms/句子结束）；
  管道输入 `read_stdin_line` 字节级 UTF-8/GBK 容错。
- token 优化：`Agent._effective_system()`/`ToolRegistry.specs()` 单 run 内缓存，
  `MemoryStore` 按 mtime+size 缓存 project context 与 facts，记忆段注入上限 30 条。
- 运行：`$env:PYTHONPATH="D:\ai-project\OhWangAgent"; .venv\Scripts\python.exe -m pytest -q`

---

## 7. 已知缺口

- memory 工具（`memory_read/write`）已接线：`default_tools(memory_store=...)` 注册，
  且 `Agent._effective_system()` 注入项目记忆上下文（CLAUDE.md/AGENTS.md + facts）。
- lsp_diagnose 已接线：cli 在 `lsp` 特性开启时经 `load_lsp_tools()` 读取 `.ohwang/lsp.json`
  注册工具；特性默认关闭（`flags.py` 默认 `lsp: False`）。
- Skill 系统已接线：`default_tools(skill_loader=...)` 注册 `skill` 工具，`build_system_prompt`
  将 `describe_all()` 注入 system prompt，agent 依据描述自动决定何时调用；用户自定义
  skill 支持 `<name>/SKILL.md`（YAML frontmatter + markdown）与 `<name>.json` 两种格式。
- Textual TUI（`tui/widgets/app.py`）为实验性，正式入口仍用 Rich REPL。
- 路线图 P3-D（Task v2 / VerifyPlanExecution）与 P4（平台化）待实现，
  详见 `docs/ROADMAP.md`。
