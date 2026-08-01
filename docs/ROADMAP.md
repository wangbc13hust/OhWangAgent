# OhWangAgent — 架构对比与演进路线图

> 基于对 Claude Code 公开泄露源码（`v2.1.88`，`Anthropic-Leaked-Source-Code`，1903 文件）的结构扫描，
> 对比 OhWangAgent 当前 MVP（`v0.2.0`，~40 文件）的能力差距，给出分阶段实现计划。

---

## 1. 扫描方法

对泄露源码做了三层扫描：
1. **顶层目录统计**：36 个子目录，记录每个目录的文件数/子目录数。
2. **注册表读取**：`tools.ts`（389 行，工具注册 + feature flag 网关）、`commands.ts`、`services/` 子目录、`skills/`、`memdir/`、`coordinator/`、`bridge/`、`hooks/`。
3. **能力归纳**：从命名 + 注册逻辑提炼功能域。

---

## 2. Claude Code 架构全景（扫描结果）

### 2.1 工具层（`tools/`，184 文件，42 个 tool）

按功能域分组（许多受 feature flag 控制）：

| 域 | 工具 |
| :--- | :--- |
| 文件/Shell | BashTool, FileReadTool, FileEditTool, FileWriteTool, GlobTool, GrepTool, NotebookEditTool, PowerShellTool |
| Web | WebFetchTool, WebSearchTool, WebBrowserTool(feature) |
| 子 Agent / 任务 | AgentTool, TaskOutputTool, TaskStopTool, TaskCreate/Get/Update/List(todo v2), TeamCreate/Delete(swarms), SendMessageTool, ListPeersTool |
| 规划 | EnterPlanModeTool, ExitPlanModeV2Tool, VerifyPlanExecutionTool |
| MCP | ListMcpResourcesTool, ReadMcpResourceTool, MCPTool |
| LSP | LSPTool |
| Skills | SkillTool |
| Worktree | EnterWorktreeTool, ExitWorktreeTool |
| 主动/调度 | SleepTool, CronCreate/Delete/List, RemoteTriggerTool, MonitorTool |
| 其他 | AskUserQuestionTool, ConfigTool, BriefTool, SyntheticOutputTool, ToolSearchTool, SnipTool, SendUserFileTool, PushNotificationTool, SubscribePRTool, REPLTool, WorkflowTool, TerminalCaptureTool |

### 2.2 服务层（`services/`，130 文件，20 子系统）

`api`、`compact`（上下文压缩）、`extractMemories`、`SessionMemory`、`mcp`、`oauth`、`lsp`、`plugins`、`policyLimits`（策略执行）、`PromptSuggestion`、`remoteManagedSettings`、`settingsSync`、`teamMemorySync`、`tools`、`toolUseSummary`、`AgentSummary`、`analytics`、`tips`、`autoDream`、`MagicDocs`。

### 2.3 其他核心系统

| 目录 | 作用 |
| :--- | :--- |
| `coordinator/` | 多 agent 协调 / swarm 模式 |
| `memdir/` | 持久化记忆：相关性检索、记忆扫描、团队记忆 |
| `skills/` | 技能工作流：bundled skills（debug/loop/simplify/verify/remember…）+ 用户技能加载 |
| `bridge/`(31) | IDE 双向通信（VS Code/JetBrains）：消息协议、权限回调、JWT、会话控制 |
| `plugins/` | 插件系统 |
| `hooks/` | toolPermission / notifs 钩子 |
| `remote/` `server/` | 远程会话 / server 模式 |
| `context/` `screens/` `components/`(389) `ink/` | React+Ink 终端 UI |
| `keybindings/` `vim/` `voice/` `buddy/` `outputStyles/` | 输入/交互增强 |
| `tasks/` `state/` `migrations/` `schemas/` | 状态/任务/配置迁移/Zod schema |
| `utils/`(564) | 庞大工具层 |

### 2.4 横切机制

- **权限系统**：Default / Plan / Auto / Bypass 四模式；deny 规则；MCP 前缀规则；permission context。
- **Feature flags**（GrowthBook + `bun:bundle` 编译期消除）：PROACTIVE、KAIROS、COORDINATOR_MODE、AGENT_SWARMS、WORKTREE_MODE、WORKFLOW_SCRIPTS、WEB_BROWSER_TOOL、TOOL_SEARCH、TODO_V2、HISTORY_SNIP 等 ~20 个。

---

## 3. OhWangAgent 当前状态（v0.2.0）

| 能力 | 状态 |
| :--- | :--- |
| Agent 循环（LLM↔tool_call） | ✅ `agent.py`，已 Mock 验证 |
| 工具 | ✅ 12 个：bash / file_read / file_write / file_edit / grep / glob / web_fetch / web_search / todo_write / enter_plan_mode / exit_plan_mode / lsp_diagnose |
| 多模型 Provider | ✅ Anthropic + OpenAI 兼容（base_url）+ 智谱 (zhipu) |
| 权限系统 | ✅ allow/ask/deny + always 记忆 + 规则文件 |
| CLI/REPL | ✅ Rich 流式 + `/help /tools /clear /auto /mode /model /todo /save /resume /exit` |
| system prompt | ✅ `prompts.py` |
| 上下文压缩 | ✅ `services/compact.py` |
| 会话持久化 / resume | ✅ `services/session.py` |
| Plan 模式 | ✅ `modes.py` + `tools/plan_mode.py` |
| Token 估算 | ✅ `services/tokens.py` |
| WebFetch | ✅ `tools/web_fetch.py` (httpx + markdownify) |
| WebSearch | ✅ `tools/web_search.py` (DuckDuckGo / Tavily) |
| AskUserQuestion | ✅ `tools/ask_user.py` |
| AgentTool 子 agent | ✅ `tools/agent_tool.py` |
| MCP 客户端 | ✅ `services/mcp.py` + CLI 接入 |
| Skill 系统 | ✅ `skills/` + bundled (debug/verify/simplify/remember) |
| Plugin 系统 | ✅ `plugins/loader.py` + entry_point 注册 |
| LSP 集成 | ✅ `services/lsp.py` + `tools/lsp_diagnose.py` |
| 持久记忆 memdir | ✅ `services/memory.py` + CLAUDE.md 风格 |
| Feature flag 体系 | ✅ `flags.py` + 环境变量 + .ohwang/flags.json |
| 完整 TUI (Textual) | ✅ `tui/widgets/app.py` |

---

## 4. 能力差距矩阵

图例：✅ 已有 · ❌ 缺失 · ⚠️ 部分

| 能力域 | Claude Code | OhWangAgent | 优先级 |
| :--- | :---: | :---: | :---: |
| Agent 循环 | ✅ | ✅ | — |
| 基础文件/Shell 工具 | ✅ | ✅ | — |
| 上下文压缩 compact | ✅ | ✅ | — |
| TodoWrite 任务追踪 | ✅ | ✅ | — |
| 会话历史 / resume | ✅ | ✅ | — |
| Plan 模式 | ✅ | ✅ | — |
| WebFetch / WebSearch | ✅ | ✅ | — |
| AskUserQuestion | ✅ | ✅ | — |
| AgentTool 子 agent | ✅ | ✅ | — |
| MCP 客户端 | ✅ | ✅ | — |
| 权限规则文件 | ✅ | ✅ | — |
| Skill 系统 | ✅ | ✅ | — |
| Plugin 系统 | ✅ | ✅ | — |
| LSP 集成 | ✅ | ✅ | — |
| 持久记忆 memdir | ✅ | ✅ | — |
| Feature flag 体系 | ✅ | ✅ | — |
| 完整 TUI（Textual） | ✅ | ✅ | — |
| **IDE bridge** | ✅ | ❌ | P3 |
| **Coordinator / swarm 多 agent** | ✅ | ❌ | P3 |
| **主动模式 / cron / 远程触发** | ✅ | ❌ | P3 |
| **Voice / Vim / Buddy** | ✅ | ❌ | P3 |
| **OAuth 认证流** | ✅ | ❌ | P3 |
| **Analytics / 遥测** | ✅ | ❌ | P3 |
| **Worktree 模式** | ✅ | ❌ | P3 |
| **Web Browser Tool** | ✅ | ❌ | P3 |

---

## 5. 演进路线图（分阶段）

### ✅ 阶段 1 — 核心完整度（P0）— 已完成

| # | 任务 | 文件 | 状态 |
| :--- | :--- | :--- | :---: |
| 1.1 | 上下文压缩 | `ohwang/services/compact.py` | ✅ |
| 1.2 | TodoWrite 工具 | `ohwang/tools/todo.py` | ✅ |
| 1.3 | 会话持久化 / resume | `ohwang/services/session.py` | ✅ |
| 1.4 | Plan 模式 | `ohwang/modes.py` + `ohwang/tools/plan_mode.py` | ✅ |
| 1.5 | Token 估算 | `ohwang/services/tokens.py` | ✅ |

### ✅ 阶段 2 — 能力扩展（P1）— 已完成

| # | 任务 | 文件 | 状态 |
| :--- | :--- | :--- | :---: |
| 2.1 | WebFetch 工具 | `ohwang/tools/web_fetch.py` (httpx + markdownify) | ✅ |
| 2.2 | WebSearch 工具 | `ohwang/tools/web_search.py` + `ohwang/services/search.py` | ✅ |
| 2.3 | AskUserQuestion 工具 | `ohwang/tools/ask_user.py` | ✅ |
| 2.4 | AgentTool 子 agent | `ohwang/tools/agent_tool.py` | ✅ |
| 2.5 | MCP 客户端 | `ohwang/services/mcp.py` | ✅ |
| 2.6 | 权限规则文件 | `ohwang/services/settings.py` | ✅ |

### ✅ 阶段 3 — 扩展机制与体验（P2）— 已完成

| # | 任务 | 文件 | 状态 |
| :--- | :--- | :--- | :---: |
| 3.1 | Skill 系统 | `ohwang/skills/` + bundled | ✅ |
| 3.2 | Plugin 系统 | `ohwang/plugins/loader.py` | ✅ |
| 3.3 | LSP 集成 | `ohwang/services/lsp.py` + `ohwang/tools/lsp_diagnose.py` | ✅ |
| 3.4 | 持久记忆 memdir | `ohwang/services/memory.py` + `ohwang/tools/memory.py` | ✅ |
| 3.5 | Feature flag 体系 | `ohwang/flags.py` | ✅ |
| 3.6 | 完整 TUI | `ohwang/tui/widgets/app.py` (Textual) | ✅ |

### 阶段 4 — 平台化（P3，按需）

| # | 任务 | 设计要点 |
| :--- | :--- | :--- |
| 4.1 | IDE bridge | VS Code / JetBrains 扩展：消息协议、权限回调、会话控制 |
| 4.2 | Coordinator / swarm | 多 agent 团队模式：TeamCreate/Delete, SendMessage, ListPeers |
| 4.3 | 主动模式 | CronCreate/Delete/List, RemoteTrigger, Monitor |
| 4.4 | Worktree | git worktree 隔离：EnterWorktree / ExitWorktree |
| 4.5 | Web Browser | Playwright / Puppeteer 驱动的浏览器工具 |
| 4.6 | OAuth 认证流 | Provider OAuth 登录 + token 刷新 |
| 4.7 | Analytics 遥测 | 使用统计 + 成本追踪 |
| 4.8 | Voice / Vim / Buddy | 输入/交互增强 |

---

## 6. 架构对齐建议（仿 Claude Code 的关键设计）

1. **统一 tool 契约**：保持 `BaseTool{name, description, input_schema, default_permission, execute}` 不变，新 tool 一律子类化注册——已与 Claude Code 一致。
2. **Provider 事件流抽象**：`BaseProvider.chat` 产出统一 `{text, tool_use, stop}` 事件，Provider 负责转换——已对齐，新增 provider 只需实现 `chat`。
3. **权限分层**：把当前内存规则升级为「规则文件 + 模式（Default/Plan/Auto/Bypass）+ 通配匹配」，对齐 Claude Code 的 permission context。
4. **Feature flag 门控**：工具注册改为 `feature()` 条件注册，便于实验性能力开关。
5. **服务化**：把 compact/session/memory/mcp/lsp 拆为 `services/` 下独立模块，Agent 持有服务引用而非内联逻辑。
6. **状态外置**：会话/任务/记忆持久化到 `.ohwang/`，支持 resume 与跨会话。

---

## 7. 建议执行顺序

```
✅ 阶段1 (P0) compact → todo → session/resume → plan mode → token估算
    ↓
✅ 阶段2 (P1) webfetch → askuser → agenttool → mcp → 权限规则文件
    ↓
✅ 阶段3 (P2) skill → plugin → lsp → memdir → flag体系 → TUI
    ↓
阶段4 (P3) 按需平台化
```

每个阶段完成后跑 `tests/` 回归 + 真实模型端到端验证，再进入下一阶段。
