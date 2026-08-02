# OhWangAgent 架构文档

> 版本：v0.3.0 · 对应代码提交 `ca4841e`（2026-08-02 第一批能力补齐批次：Git 上下文注入 / 危险命令模式检测 / /cost 见 §3.5/3.6/3.8；flags 真值大小写修复见 CHANGELOG）· 533 测试全绿
> （覆盖率 91%，实测命令：`coverage run --source=ohwang -m pytest` + `coverage report --omit="ohwang/tui/widgets/*"`）
>
> 定位：交互式 CLI **办公 agent** —— 文档撰写、会议纪要、资料检索、任务管理、
> 报告生成 + 软件工程能力。架构对齐 Claude Code（Agent 循环 + 工具注册表 +
> 权限/钩子/策略/记忆/调度机制），Provider 层可插拔，覆盖 6 家模型。

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  ohwang/cli.py        REPL + 一次性任务 + /命令 + cron + 记忆提取    │
│                       + PromptSuggestion 启动建议 + .env 加载        │
│  ohwang/tui/render.py Rich 流式渲染（UTF-8 控制台）                │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/agent.py      Agent 循环：LLM → tool_use → 执行 → 回灌      │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/providers/    统一事件流（text / tool_use）+ token 用量归账   │
│    base.py → anthropic_provider → openai_provider(6 家兼容)       │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/tools/        BaseTool 注册表（约 39 个工具，按依赖启停）     │
├─────────────────────────────────────────────────────────────────┤
│  ohwang/services/     横切服务：记忆/钩子/策略/调度/会话/压缩/LSP/…  │
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
cli.main() ── build_agent() 装配 Agent/渲染器/服务/TaskStore/调度器
  │            （无历史时输出 _suggest_prompts() 规则式启动建议）
  ▼
agent.run(prompt)
  │  ① 追加 user 消息 → ② microcompact() 裁剪超限 tool_result（>30K 字符）
  │  ③ 需要时上下文压缩（阈值由窗口派生，熔断硬裁兜底）
  │  ④ provider.chat() 产出事件流（text / tool_use），流式归账 token
  │        └─ Reactive 压缩：API 抛 PTL 错误 → 当回合摘要旧消息后重试（至多一次）
  │  ⑤ 收集 tool_use → 逐条 _run_tool()
  │        ├─ hooks.run_pre_tool   （可阻断/改写输入）
  │        ├─ permissions.can_run  （模式 + 规则）
  │        ├─ policy.check_tool    （调用上限）
  │        ├─ tool.execute(input)  （执行）
  │        └─ usage.record / hooks.run_post_tool
  │  ⑥ tool_result 回灌为 user 消息 → 循环直到无 tool_use
  ▼
最终文本 → renderer 流式输出
  ▼
cli._run_once() 收尾 → MemoryExtractor.maybe_extract() 自动记忆
```

---

## 2. 目录结构

```
ohwang/
├── cli.py                 入口：参数解析、装配、REPL、/命令、一次性任务、.env 加载、
│                          PromptSuggestion、build_agent（run_lock 注入）
├── __main__.py            python -m ohwang 入口
├── agent.py               Agent 循环核心
├── config.py              PROVIDER_PRESETS + Config 数据类
├── flags.py               FeatureFlags（env + .ohwang/flags.json + 默认）
├── modes.py               Mode 枚举（default/plan/auto/bypass）
├── permissions.py         PermissionManager 权限决策
├── prompts.py             System prompt 构建
│
├── providers/             模型层
│   ├── base.py            BaseProvider（事件流协议 + usage_* 计数）
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
│   ├── file_diff.py       file_diff（纯预览）+ file_preview_edit（预览→审批→应用）
│   ├── multi_edit.py      multi_edit（一次调用批量替换多文件，preview/apply 双模式）
│   ├── web_fetch.py / web_search.py / web_browser.py   Web
│   ├── tool_search.py     工具检索（把 registry 作为工具暴露）
│   ├── todo.py            TodoWriteTool + TodoStore（扁平内存清单）
│   ├── tasks.py           TaskStore + task_create/get/update/list/stop/output
│   │                      （结构化任务，持久化 .ohwang/tasks/*.json）
│   ├── verify_plan.py     VerifyPlanExecutionTool（计划执行按步校验）
│   ├── plan_mode.py       enter/exit_plan_mode
│   ├── ask_user.py        ask_user_question
│   ├── agent_tool.py      子 agent（agent_factory）
│   ├── schedule.py        cron_create/delete/list
│   ├── worktree.py        enter/exit_worktree
│   ├── config.py          config（运行时权限规则）
│   ├── sleep.py / synthetic_output.py / brief.py / snip.py   P3-C 输出类
│   ├── send_user_file.py  send_user_file（交付文件给用户，不进模型上下文）
│   ├── memory.py          memory_read/write（经 default_tools(memory_store=...) 注册）
│   └── lsp_diagnose.py    lsp_diagnose（经 load_lsp_tools() 注册，读取 .ohwang/lsp.json）
│
├── services/             横切服务
│   ├── window.py          上下文窗口解析（env OHWANG_MAX_CONTEXT_TOKENS > config > preset > 默认）
│   ├── compact.py         上下文压缩（阈值由窗口派生）、reactive 压缩辅助、熔断硬裁、microcompact
│   ├── tokens.py          token 估算（CJK 按 ~1 字符/token）
│   ├── session.py         会话保存/resume（.ohwang/sessions/）
│   ├── summarizer.py      会话摘要蒸馏（/save 时生成，复用 Compactor 序列化）
│   ├── settings.py        权限规则文件读写
│   ├── search.py          Tavily → Bing(默认,国内可达) → DuckDuckGo 回退
│   ├── mcp.py             MCP 客户端 + 工具封装
│   ├── worktree.py        git worktree 管理
│   ├── scheduler.py       cron 调度器（proactive 模式，state_file 持久化 .ohwang/cron.json）
│   ├── browser.py         Playwright 浏览器会话
│   ├── memory.py          MemoryStore（分层 project/全局 + 类型分级 + 相关性排名）
│   │                       + MemoryExtractor（自动记忆提取，user 路由 + 游标持久化）
│   ├── hooks.py           HookManager（pre/post/notif）
│   ├── policy.py          PolicyLimits（调用上限）
│   ├── summary.py         UsageTracker（工具调用统计）
│   └── lsp.py             LSPClient（stdio JSON-RPC，textDocument/diagnostic）
│
├── skills/               Skill 加载器（.ohwang/skills/，SKILL.md 目录格式 + JSON 兼容）
│   └── bundled/          内置 skill：debug / remember / simplify / verify
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
2. 每回合先 `microcompact()` 裁剪超限（>30K 字符）tool_result 为
   `[Old tool result content cleared (was N chars)]`，防巨型工具输出拖垮上下文。
3. 达到压缩阈值时用 `Compactor` 压缩历史；阈值默认由模型上下文窗口派生
   （`window − 20K 输出余量 − 13K 缓冲`，下限 4K），窗口缺省时回退
   `DEFAULT_THRESHOLD_TOKENS=100_000`，`--compact-threshold` 显式值优先。
   摘要连续 3 次失败触发熔断 → 放弃摘要、硬裁旧消息（snip）。
4. `provider.chat(system, messages, tools, max_tokens)` 产出事件流：
   - `text` → 追加到正文并流式渲染；
   - `tool_use` → 收集。
   **Reactive 压缩**：若 API 抛 "prompt too long" 类错误，当回合内 `compact()` 摘要
   旧消息后重试同一次 chat（至多一次，镜像 Claude Code withheld-413 路径）。
5. 有 `tool_use` 则每条经 `_run_tool()` 执行（见下），结果组装为一条
   `user` 消息回灌；无 `tool_use` 即结束。
6. `_run_tool()` 调用链：**hook(pre) → 权限 → policy → 执行 → 统计/后置钩子**，
   工具抛异常兜底为 `is_error` 结果块而非让循环崩溃。

状态：`agent.messages`（会话历史）、`agent.iterations`、`agent.usage`。
`_effective_system()` 在单 run 内缓存 system + todo + 记忆上下文。

### 3.2 Provider 层（`ohwang/providers/`）

- `BaseProvider.chat(...)` 是唯一抽象接口，产出统一事件流字典
  `{"type": "text"|"tool_use", ...}`；基类持有 `usage_prompt/completion/calls`
  计数器与 `usage_report()`，供 `/summary`、`/cost` 展示。
- `AnthropicProvider`：Anthropic 原生 tool_use 协议直通，从 `message_start`/
  `message_delta` 归账 token；默认开启 prompt caching（`system` 转 block 列表挂
  `cache_control`，末条消息末 content block 加断点，浅拷贝不污染调用方），
  `DISABLE_PROMPT_CACHING=1` 可关。DeepSeek/OpenAI 服务端自动缓存，无需客户端改动。
- `OpenAIProvider`：把 tool_use 事件 ↔ OpenAI function-calling 转换，流式增量按
  index 累积，`stream_options.include_usage` 归账 token，因此任何 OpenAI 兼容
  端点（DeepSeek/Kimi/Qwen/智谱/本地模型）都可直接接入。
- 6 家预设见 `config.py::PROVIDER_PRESETS`（env 变量、默认模型、base_url）。

### 3.3 工具层（`ohwang/tools/`）

每个工具是 `BaseTool` 子类，声明四要素：

| 属性 | 含义 |
| :--- | :--- |
| `name` | 工具名（发给模型） |
| `description` | 使用说明 |
| `input_schema` | JSON Schema |
| `default_permission` | `allow` / `ask` / `deny` 缺省权限 |

`default_tools(...)` 按依赖装配注册表：**约 39 个工具**（含 browser 时 40）。
核心与展示类工具无条件注册；todo / task / memory / skill / plan_mode / ask_user /
agent / worktree / cron / browser / web_search 仅在传入对应依赖时注册。
`ToolSearchTool` 把注册表本身暴露为可搜索工具。

**新增工具族（v0.3.0 后半段）：**

| 工具 | 职责 | 默认权限 |
| :--- | :--- | :--- |
| `file_diff` | 纯预览 unified diff（difflib，无三方依赖） | allow |
| `file_preview_edit` | 预览→审批→应用单文件编辑，仅显式 `apply=true` 写盘 | ask |
| `multi_edit` | 一次调用批量替换多文件，preview/apply 双模式，歧义/缺失/空串安全跳过 | ask |
| `task_create/get/update/list/stop/output` | Task v2 结构化任务 CRUD（区别于扁平 todo，带输出捕获与跨会话持久化） | allow |
| `verify_plan_execution` | 计划执行后按步校验（done/partial/missed + evidence），有 missed 置 error | allow |
| `send_user_file` | 交付文件给用户在终端展示，内容**不进模型上下文** | allow |

### 3.4 权限系统（`ohwang/permissions.py` + `modes.py`）

- 四种模式：`DEFAULT`（按 default_permission + ask 回调）、`PLAN`（只读，
  仅 `allow` 工具与声明了 `read_only_actions` 的工具通过，`exit_plan_mode`
  退出读保护模式需用户批准）、`AUTO`（全部放行）、`BYPASS`（完全跳过）。
- 规则（`.ohwang/settings.json`）：`allow/ask/deny` 三列表，支持 glob
  （如 `mcp__*`），优先级 **deny > allow > ask > 工具默认**，且 deny 优先于
  always 记忆。
- `always` 记忆：用户对某调用回答 "always" 后，按 `工具名::参数` 签名
  永久放行；退出 PLAN 模式自动还原进入前的模式。
- PLAN 模式特判（实测修复）：`exit_plan_mode` 走 `_ask_approved` 用户批准
  （非交互 stdin 默认 deny，读保护模式不可被模型自行退出）；`config` 的
  `list/get` 只读动作放行，`allow/remove` 等变更动作仍拦截。

### 3.5 服务层（`ohwang/services/`）

| 服务 | 职责 | 数据 |
| :--- | :--- | :--- |
| `window` | `effective_context_window(config)`：解析有效上下文窗口，优先级 env `OHWANG_MAX_CONTEXT_TOKENS` > config > 默认 128K；压缩阈值由此派生 | — |
| `tokens` | 本地 token 估算（拉丁 ~4 字符/token，CJK ~1 字符/token + 每消息/块开销），供压缩阈值与预算判断，非精确分词 | — |
| `git_context` | 采集当前分支 / 最近 5 条提交 / 工作区状态，注入 `Agent._effective_system()`（非仓库或失败静默返回空串；TTL 5s 缓存防每轮重建重复 spawn git 子进程） | — |
| `MemoryStore` | 分层持久记忆：项目层 `{workdir}` + 全局层 `~/.ohwang`（懒创建）；事实带 `type`（user/feedback/project/reference）；`render_context(query)` 空 query 注入每层最新 ≤30 条，带 query 按确定性相关性打分取 top-10（修复"注入最新 30 条"与双重头） | `CLAUDE.md`/`AGENTS.md` + `.ohwang/memory/facts.json`（+ `~/.ohwang/memory/facts.json`） |
| `MemoryExtractor` | 会话增长 ≥20 条时让模型提炼事实自动入库；提取提示强制 4 类型分类并排除单会话临时内容（会议记录/一次性数据图表）；`type=user` 自动路由到全局层；游标 `extract_cursor.json` 跨会话持久化防重复提取 | `.ohwang/memory/facts.json` + `extract_cursor.json` |
| `HookManager` | pre/post tool + notif 生命周期钩子 | `.ohwang/hooks.json` 命令钩子 |
| `guards` | 内置安全守卫：pre_tool_use 规则阻断危险 shell 命令（`rm -rf /`、`git push --force`、磁盘格式化、fork bomb、系统关机等，词边界防误伤）；flag `dangerous_command_guard` 默认开启 | — |
| `PolicyLimits` | 工具调用总量/单工具上限，防失控循环；构造默认 200，`policy.json` 存在但缺 `max_tool_calls` 键时 `load()` 回退 **1000**（两路径默认值分歧，见 PROJECT_REVIEW）；**被权限拒绝的调用也计入预算**（防拒绝后无限重试） | `.ohwang/policy.json` |
| `UsageTracker` | 工具调用统计（`/summary`、brief 工具） | 内存 |
| `cost` | `/cost` 美元成本估算：按 (provider, model) 价格表（USD/1M tokens）× provider 已归账 token（`usage_report()`）；未知模型返回 None 显示 `unknown` | — |
| `Compactor` | 上下文压缩：阈值由 `context_window` 派生（显式 `threshold_tokens` 优先）；熔断（连续 3 次摘要失败 → snip 硬裁）；`is_prompt_too_long_error` 识别 PTL；`microcompact` 裁剪超限工具结果 | 阈值派生自 `services/window.py` |
| `SessionStore` | 会话保存/resume（`save` 可带 `summary`；`/save` 经 `SessionSummarizer` 蒸馏简报，`/resume` 注入为 `# Session Context` 块） | `.ohwang/sessions/*.json` |
| `SessionSummarizer` | 会话摘要蒸馏：复用 `Compactor._serialize` 转录、截断 80K 字符，LLM 失败静默返回 `""` | — |
| `settings` | `.ohwang/settings.json` 权限规则 CRUD（allow/ask/deny glob 列表，幂等追加，无内存缓存） | `.ohwang/settings.json` |
| `Scheduler` | cron 调度，agent 空闲时可后台执行任务；**state_file 持久化，重启不丢** | `.ohwang/cron.json` |
| `MCPClient` | 外部 MCP 服务器工具 | `.ohwang/mcp.json` |
| `SearchProvider` | Tavily(有key) → Bing(默认,国内可达) → DDG 回退；不可达抛 `SearchError` | — |
| `WorktreeManager` | git worktree | — |
| `BrowserSession` | Playwright 浏览器 | — |
| `LSPClient` | stdio JSON-RPC 诊断（pyright/pylsp/TS…），`load_lsp_tools()` 按 `.ohwang/lsp.json` 注册 `lsp_diagnose` | `.ohwang/lsp.json` |

> 内部依赖仅两条边：`summarizer → compact → tokens`（其余模块互为叶节点，互不 import）；
> services 对外被 `cli.py`/`agent.py`/`tools/*` 消费，见 §2 目录结构与 §3.8 装配。

### 3.6 配置与开关

- `config.py::Config`：provider/model/api_key/max_tokens/工作目录/`context_window`/
  `compact_threshold` 等，`resolve()` 用环境变量补齐、并从 preset 填充 `context_window`
  （zhipu/openai/deepseek 128K、anthropic 200K、kimi 8_192、qwen 32K）；`--context-window`
  与 `OHWANG_MAX_CONTEXT_TOKENS` 可覆盖。
- `flags.py::FeatureFlags`：三级覆盖 `OHWANG_FEATURE_<NAME>` env →
  `.ohwang/flags.json` → 内置默认。env 真值经 `_env_truthy()` 解析：`strip().lower()`
  后 ∈ `("1","true","yes")` 即真（大小写不敏感，`TRUE`/`True`/`YES` 均生效，
  `f741a5e` 修复前仅小写三值生效）。默认开启 web_fetch/web_search/web_browser/
  ask_user/agent_tool/mcp/skill/memory/todo/plan_mode/compact/session/worktree/
  tool_search/proactive/dangerous_command_guard；默认关闭 lsp/plugin/coordinator/
  agent_swarms/workflow_scripts。
- `settings.py`：`.ohwang/settings.json` 权限规则读写（`config` 工具可运行时改）。

### 3.7 渲染与编码（`ohwang/tui/render.py`）

- `Renderer` 基于 Rich：流式文本、工具调用高亮、ask 交互。
- `setup_utf8()`：Windows 下 `SetConsoleOutputCP(65001)` + stdout/stderr
  强制 UTF-8，解决 GBK 控制台中文乱码；管道输入 `read_stdin_line` 字节级
  UTF-8/GBK 容错。

### 3.8 CLI 装配（`ohwang/cli.py`）

- `main()` 先 `_prepare_workdir(args)`：`chdir` 到 `--workdir` 并把 `args.workdir`
  规范化为绝对路径（服务层相对 cwd 二次解析会嵌套 `.ohwang/`）；`build_agent`
  再兜底 `abspath(args.workdir or cwd)`。
- 非交互一次性任务（`-p`）且未给 `-y`/`--plan` 时，stderr 打印提示（非交互
  stdin 下 ask 工具默认 deny，可能让工具全部被拒）。
- `build_agent(args, run_lock)`：**`main` 传入唯一 `run_lock`**，REPL 前台与
  cron 调度后台共用，避免并发 `run()` 污染 `messages`；`scheduler.start()` 在
  `agent` 装配完成后才调用。
- 装配顺序：Config.resolve → create_provider → Renderer → FeatureFlags →
  PermissionManager（mode 由 `--plan`/`-y` 推导）→ TodoStore/TaskStore/Usage/
  MemoryStore/MemoryExtractor → SessionSummarizer → SkillLoader → system_prompt →
  Scheduler（runner=`_run_locked`）→ `default_tools(...)` → MCP/LSP 扩展 →
  Compactor → SessionStore → HookManager/PolicyLimits → `agent = Agent(...)`。
- 子 agent（`_agent_factory`）使用独立 AUTO `PermissionManager`，继承主 agent
  的 policy/compactor/usage/hooks，防子 agent 篡改主权限状态。
- `_suggest_prompts()`：无历史时基于 todo/文件/记忆/迭代数给 3 条规则式
  启动建议（零 API 调用）。

---

## 4. `.ohwang/` 数据目录

| 文件/目录 | 内容 |
| :--- | :--- |
| `settings.json` | 权限规则 allow/ask/deny |
| `policy.json` | 工具调用上限 |
| `hooks.json` | 生命周期命令钩子 |
| `flags.json` | 特性开关覆盖 |
| `cron.json` | 定时任务持久化（重启不丢） |
| `lsp.json` | LSP 服务器配置（command/args/servers） |
| `memory/facts.json` | 自动/手动记忆事实 |
| `memory/extract_cursor.json` | 记忆提取游标（跨会话防重复提取） |
| `sessions/*.json` | 会话历史 |
| `worktree.json` | WorktreeManager 自建工作树状态 |
| `tasks/*.json` | Task v2 结构化任务对象（id/标题/描述/状态/父任务/输出/时间戳） |
| `snips/*.txt` | snip 工具保存的输出片段 |
| `skills/` | Skill 定义：`<name>/SKILL.md`（YAML frontmatter + markdown）或 `<name>.json` |
| `mcp.json` | MCP 服务器列表 |

---

## 5. 扩展点

- **加工具**：在 `ohwang/tools/` 新建 `BaseTool` 子类，并在 `default_tools()`
  中注册（或按依赖条件注册，如 task/memory/skill 族）。
- **加模型**：在 `PROVIDER_PRESETS` 增加预设；若 OpenAI 兼容则零代码接入，
  否则实现 `BaseProvider`。
- **加服务**：在 `ohwang/services/` 新增模块，从 `services/__init__.py` 导出，
  在 `cli.build_agent()` 装配。
- **加特性开关**：`flags.py::_DEFAULTS` 增一项，代码里用 `flags.is_enabled()` 门控。

---

## 6. 测试架构（`tests/`，53 个文件 / 533 个用例，覆盖率 91%）

- `helpers.py`：`ScriptedProvider`（重放事件序列）、`MockSearchProvider`、
  `build_agent()`——无网络、无真实模型的集成测试基座。
- 并发/接线约定：`cli.build_agent(args, run_lock)` 由 `main` 传入唯一锁，
  REPL 前台与 cron 调度后台共用；`scheduler.start()` 在 `agent` 装配完成后才调用。
  子 agent 使用独立 AUTO `PermissionManager` 并继承主 agent 的
  policy/compactor/usage/hooks。
- 覆盖：工具单元测试、provider 转换、权限/plan 模式、压缩、会话、记忆/记忆提取、
  hooks/policy/usage、调度、worktree、MCP、Skill/Plugin、办公场景
  （`test_scenarios.py`）、P3 新工具、以及：`test_file_diff.py`、
  `test_multi_edit.py`、`test_send_user_file.py`、`test_tasks.py`、
  `test_verify_plan.py`、`test_tui.py`、`test_fixes_review.py`（真实办公场景
  实测修复批次回归：workdir 规范化/权限硬边界/plan 退出批准/config 只读/
  记忆阈值/非交互告警）；上下文系统批次新增 `test_window.py`、
  `test_microcompact.py`（窗口派生阈值/熔断/PTL 匹配/microcompact）；
  分层记忆批次新增 `test_memory_layers.py`、`test_memory_extract.py`、
  `test_session.py`；`test_flags.py` 追加 2 个 env 真值大小写用例
  （`f741a5e` 修复回归）；第一批能力补齐新增 `test_git_context.py`、
  `test_guards.py`、`test_cost.py`（Git 注入/危险命令守卫//cost）。
- 覆盖率 91%（`coverage run --source=ohwang -m pytest` 后
  `coverage report --omit="ohwang/tui/widgets/*"` 实测；按模块补齐：
  `test_providers.py`、`test_mcp.py`、`test_browser.py`、`test_lsp.py`、
  `test_hooks.py`、`test_search.py`、`test_plugin.py`、`test_gaps.py`（分支补齐））。
- MCP 用真实 stdio fake server 子进程测 JSON-RPC 握手；Playwright 用 mock
  `playwright` + `playwright.sync_api` 模块；LSP 用子进程 + 桩响应。
- 流式：`Renderer.stream_text` 即时输出 + 智能 flush（128字符/50ms/句子结束）；
  管道输入 `read_stdin_line` 字节级 UTF-8/GBK 容错。
- token 优化：`Agent._effective_system()`/`ToolRegistry.specs()` 单 run 内缓存，
  `MemoryStore` 按 mtime+size 缓存 project context 与两层 facts；`render_context()`
  空 query 注入每层 ≤30 条，带 query 时按相关性取 top-10 且跳过缓存。
- 运行：`$env:PYTHONPATH="D:\ai-project\OhWangAgent"; .venv\Scripts\python.exe -m pytest -q`

---

## 7. 已知缺口

- memory 工具（`memory_read/write`）已接线：`default_tools(memory_store=...)` 注册，
  且 `Agent._effective_system()` 注入项目记忆上下文（CLAUDE.md/AGENTS.md + facts）。
- lsp_diagnose 已接线：cli 在 `lsp` 特性开启时经 `load_lsp_tools()` 读取
  `.ohwang/lsp.json` 注册工具；特性默认关闭（`flags.py` 默认 `lsp: False`）。
- Skill 系统已接线：`default_tools(skill_loader=...)` 注册 `skill` 工具，
  `build_system_prompt` 将 `describe_all()` 注入 system prompt；支持
  `<name>/SKILL.md`（YAML frontmatter + markdown）与 `<name>.json` 两种格式，
  内置 debug/remember/simplify/verify 四个 bundled skill。
- Textual TUI（`tui/widgets/app.py`）为实验性，正式入口仍用 Rich REPL。
- `cli.build_agent` 中 `_agent_factory`/`_run_locked` 存在闭包前向引用
  （引用后文才定义的 `agent`/`compactor`/`hooks`/`policy`），靠晚绑定可运行，
  但重排装配顺序会引入启动期风险（见 `docs/PROJECT_REVIEW.md` §3.1，建议显式注入）。
- 主/子 agent 共享 Provider 对象，Provider 级 token 统计会混入（见评审 §3.2）。
- 白领一天工作流实测暴露项（2026-08-02，详见 CHANGELOG 该日章节）：`memory_read`
  多词查询命中弱（`"key1 key2"` 语义过滤未命中刚写入的 fact，需 `scope=all` 全量读取
  兜底）；`| tail` 管道缓冲下后台任务无进度反馈、易被误判卡死；`web_browser` 依赖
  playwright（未安装时仅 web_search/web_fetch 可用）；Bash 分类器后端间歇性不可用
  （`deepseek-v4-flash is temporarily unavailable`，等待+重试可恢复）。
- 路线图 P4（平台化：IDE bridge / swarm / OAuth / 遥测 / remote-server /
  NotebookEdit / 命令历史补全）待实现，详见 `docs/ROADMAP.md`。
