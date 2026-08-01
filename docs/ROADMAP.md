# OhWangAgent — 架构对比与演进路线图

> 基于对 Claude Code 泄露源码（`v2.1.88`，`Anthropic-Leaked-Source-Code`，1903 文件）的结构扫描，
> 与 OhWangAgent 当前实现（`v0.3.0`，88 个 Python 文件，222 测试全绿）对比，给出修正后的演进计划。
>
> **定位**：办公 agent（办公 Agent）——文档处理、会议纪要、资料检索、任务管理、报告撰写 + 软件工程能力。

---

## 1. 当前能力盘点（2026-08 实测）

### 1.1 工具层（27 个）

| 域 | 工具 |
| :--- | :--- |
| 文件/Shell | bash, powershell, file_read, file_write, file_edit, grep, glob |
| Web | web_fetch, web_search, browser_action(Playwright, 按 flag) |
| 记忆/任务 | memory_read, memory_write, todo_write |
| 规划/协作 | enter_plan_mode, exit_plan_mode, agent(子 agent) |
| 主动/调度 | cron_create, cron_delete, cron_list |
| 输出/展示 | synthetic_output, brief, snip, sleep |
| MCP | load_mcp_tools（CLI 接入） |
| 其他 | ask_user_question, tool_search, lsp_diagnose, enter_worktree, exit_worktree, config |

### 1.2 服务层（11 个）

compact（上下文压缩）、session（会话/resume）、tokens（token 估算）、settings（权限规则文件）、
search（DuckDuckGo/Tavily）、mcp、worktree、scheduler（cron）、browser、memory（持久记忆）、lsp。

### 1.3 其他系统

- **权限**：Default / Plan / Auto / Bypass 四模式 + `.ohwang/settings.json` allow/ask/deny 通配 + always 记忆 + plan 模式还原
- **Provider**：anthropic / openai / zhipu / deepseek(v4-flash|v4-pro) / kimi / qwen（6 家，均 OpenAI 兼容或直连）
- **Feature flag**：`flags.py` 环境变量 + `.ohwang/flags.json` 三级覆盖
- **Skills / Plugins / LSP / 持久记忆 / 完整 TUI(Textual)**：✅

---

## 2. 能力差距矩阵（对 Claude Code）

图例：✅ 已有 · ❌ 缺失 · ⚠️ 部分

| 能力域 | Claude Code | OhWangAgent | 优先级 |
| :--- | :---: | :---: | :---: |
| Agent 循环 | ✅ | ✅ | — |
| 基础文件/Shell 工具 | ✅ | ✅ | — |
| PowerShell / Notebook | ✅ | ⚠️ 仅 PowerShell | P4 |
| 上下文压缩 | ✅ | ✅ | — |
| TodoWrite 任务追踪 | ✅ | ✅ | — |
| **Task v2（Create/Get/Update/List/Stop/Output）** | ✅ | ❌ | P3 |
| 会话历史 / resume | ✅ | ✅ | — |
| Plan 模式 | ✅ | ✅ | — |
| **VerifyPlanExecutionTool** | ✅ | ❌ | P3 |
| WebFetch / WebSearch / Browser | ✅ | ✅ | — |
| AskUserQuestion | ✅ | ✅ | — |
| AgentTool 子 agent | ✅ | ✅ | — |
| MCP 客户端 | ✅ | ⚠️ 无 resource 工具 | P4 |
| 权限规则文件 | ✅ | ✅ | — |
| Skill / Plugin / LSP / 记忆 | ✅ | ✅ | — |
| Feature flag / TUI | ✅ | ✅ | — |
| Worktree | ✅ | ✅ | — |
| Cron 调度 | ✅ | ✅ | — |
| **Sleep / Monitor / RemoteTrigger** | ✅ | ⚠️ Sleep 已实现 | P3 |
| **ToolSearch** | ✅ | ✅ | — |
| **SyntheticOutput / Brief / Snip / SendUserFile** | ✅ | ⚠️ 3/4 | P3 |
| **ConfigTool** | ✅ | ✅ | P3 |
| **自动记忆提取（extractMemories）** | ✅ | ✅ | **P3-高** |
| **hooks（preToolUse/postToolUse/notifs）** | ✅ | ✅ | **P3-高** |
| **toolUseSummary / AgentSummary** | ✅ | ✅ | P3 |
| **policyLimits 策略执行** | ✅ | ✅ | P3 |
| **PromptSuggestion** | ✅ | ❌ | P3 |
| IDE bridge / swarm / OAuth / 遥测 | ✅ | ❌ | P4 |

---

## 3. 修正后演进路线图

> 按「办公 agent」定位重新排序：记忆连续性与机制完备优先，平台化按需。

### ✅ P0 — 核心完整度（已完成）

compact、todo_write、session/resume、plan mode、token 估算、权限四模式+规则文件。

### ✅ P1 — 能力扩展（已完成）

web_fetch、web_search、ask_user、agent、mcp 客户端、settings 权限文件、web_fetch。

### ✅ P2 — 扩展机制与体验（已完成）

skill、plugin、lsp、memdir 记忆、feature flag、Textual TUI、powerShell、tool_search、worktree、cron 调度、browser(flag)、DeepSeek v4 provider。

### ✅ P3-A — 记忆与上下文（已完成）

| # | 任务 | 说明 | 状态 |
| :--- | :--- | :--- | :---: |
| 3A.1 | **自动记忆提取 extractMemories** | `MemoryExtractor` 会话/增长时提炼关键事实，自动写入 `.ohwang/memory/` | ✅ |
| 3A.2 | **toolUseSummary / AgentSummary** | `UsageTracker` 工具调用统计 + `/summary` 命令 | ✅ |
| 3A.3 | PromptSuggestion | 会话首轮提示用户可用的记忆/快捷命令 | 📋 |

### ✅ P3-B — 钩子与策略（已完成）

| # | 任务 | 说明 | 状态 |
| :--- | :--- | :--- | :---: |
| 3B.1 | **hooks 系统** | `HookManager`：pre/post tool + notif，`.ohwang/hooks.json` 命令钩子 | ✅ |
| 3B.2 | **policyLimits** | `PolicyLimits`：工具调用频率/总量上限，`.ohwang/policy.json` | ✅ |
| 3B.3 | **ConfigTool** | 运行时读写 `.ohwang/settings.json` 权限规则（`config` 工具） | ✅ |

### ✅ P3-C — 输出与展示（已完成）

| # | 任务 | 说明 | 状态 |
| :--- | :--- | :--- | :---: |
| 3C.1 | SyntheticOutputTool | 向用户展示文本，不进模型上下文 | ✅ |
| 3C.2 | BriefTool | 会话进度简报（工具统计/todo/迭代数） | ✅ |
| 3C.3 | SleepTool | 主动模式下延时等待 | ✅ |
| 3C.4 | SnipTool | 保存终端输出片段到 `.ohwang/snips/` | ✅ |

### 📋 P3-D — 任务与协作增强

| # | 任务 | 说明 |
| :--- | :--- | :--- |
| 3D.1 | Task v2（Create/Get/Update/List/Stop/Output） | 结构化任务对象替代纯 todo 列表 |
| 3D.2 | VerifyPlanExecutionTool | 计划完成后校验执行结果 |

### 📋 P4 — 平台化（按需）

IDE bridge、Coordinator/swarm、OAuth、遥测分析、NotebookEdit、MCP resource、remote/server。

---

## 4. 执行顺序（修订）

```
✅ P0 → P1 → P2（记忆/工具/机制完备，180 测试）
   ↓
✅ P3-A 自动记忆提取 → 使用摘要        （MemoryExtractor + /summary）
   ↓
✅ P3-B hooks 系统 → policyLimits → ConfigTool   （212 测试全绿）
   ↓
✅ P3-C 输出展示工具（SyntheticOutput/Brief/Sleep/Snip）   （222 测试全绿）
   ↓
📋 P3-D Task v2 → VerifyPlanExecution
   ↓
📋 P4 平台化（按需）
```

每批完成后跑 `tests/` 回归 + 真实模型端到端验证，再进入下一批。
