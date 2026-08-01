# OhWangAgent vs Claude Code 能力差距分析

> 日期：2026-08-02
> 方法：对两个项目的完整代码扫描（OhWangAgent 80 个 Python 源文件 / Anthropic-Leaked-Source-Code 1931 个 TypeScript 文件）
> 参考基线：`D:\ai-project\Anthropic-Leaked-Source-Code`

## 总览

OhWangAgent 的核心机制已经相当齐全——**agent 循环、压缩、记忆、权限、MCP、skills、子 agent、cron、任务系统这些骨架都有**。差距主要在**精度、深度、工程完备性**三个层面：Claude Code 在每个子系统上都多走了几步，而这几步恰恰是产品级与教学级的差别。

## 能力矩阵

| # | 维度 | OhWangAgent | Claude Code | 差距 |
|---|------|-------------|-------------|------|
| 1 | **Agent 循环** | 流式工具调用循环，50 次迭代上限，错误捕获返回 `is_error` | QueryEngine，prompt caching（CacheScope）、缓存失效检测 | ⚠️ 中 — **无 API 级 prompt caching** |
| 2 | **上下文管理** | 启发式 token 估算（4字符/token），LLM 摘要压缩，保留最近6条 | 精确 token 统计，200K/1M 窗口感知，**reactive compact**（回合中压缩）、context collapse、token budget（+500k 续跑） | 🔴 大 — 估算不精确，无窗口感知，无回合中压缩 |
| 3 | **记忆** | facts.json + CLAUDE.md，LLM 自动提取（20条延迟），**关键词搜索** | MEMORY.md 索引 + topic 文件，4 类型分类，**side-query 相关性选择**，团队记忆，SESSION.md | ⚠️ 中 — 无相关性选择，无类型体系 |
| 4 | **权限安全** | 4 模式 + allow/ask/deny glob 规则 | + **YOLO 自动放行分类器**、路径验证、**危险命令模式检测**、**OS 沙箱**（文件/网络隔离）、shadowed rule 检测 | 🔴 大 — 无沙箱、无参数/路径级规则、无危险模式检测 |
| 5 | **MCP** | stdio JSON-RPC 客户端，仅 tools | stdio+SSE+HTTP 三传输，OAuth，resources/prompts，工具搜索，官方 registry | ⚠️ 中 — 传输单一，无 resources/prompts |
| 6 | **Skills/插件** | SKILL.md + 插件 entry_point，4 个内置 skill | 17 内置 skill，MCP skill builder，**插件 marketplace**，skill 搜索 | 🟢 小 — 架构接近，缺生态 |
| 7 | **子 agent** | AgentTool 顺序委托，无并行 | Task 工具套件（6个），**并行 fan-out**，agent 定义文件，**team/swarm**，coordinator 模式，SendMessage | 🔴 大 — 无并行任务，无团队 |
| 8 | **工具集** | ~35-40 个（覆盖面很广） | 30+，多出 NotebookEdit、computer use、push notification、REPL | 🟢 小 — 覆盖面已对齐，缺个别 |
| 9 | **Hooks** | 3 事件（pre/post_tool_use, notif） | **27 事件**，4 种后端（prompt/agent/HTTP/命令），structured output | 🔴 大 — 事件广度不足 |
| 10 | **UI** | Rich REPL + 实验性 Textual TUI | Ink TUI，**vim 模式、keybindings、主题系统**、statusline、100+ 斜杠命令 | ⚠️ 中 — 交互深度差距 |
| 11 | **Git** | worktree 管理 | **git 状态/分支/提交注入 system prompt**、diff 组件、/commit /review /branch | ⚠️ 中 — 无 git 上下文，无 commit 工作流 |
| 12 | **远程** | 无（P4） | 远程沙箱、WebSocket、teleport 迁移、bridge 无头模式 | 🔴 大 — 全缺（已列路线图） |
| 13 | **Provider** | **6 预设**（zhipu/anthropic/openai/deepseek/kimi/qwen）✅ | Anthropic + Bedrock + Vertex + Foundry，**主/侧模型分离**（side-query 用小模型） | 🟢 小 — 多 provider 反而是优势；缺侧模型路由 |
| 14 | **成本** | token/调用计数，**无美元计算** | 价格表、/cost /usage、**预算强制**（maxBudgetUsd） | ⚠️ 中 — 缺成本表与预算 |
| 15 | **设置** | .ohwang/settings.json + 三级 flags | user/project/managed 多层合并，Zod 校验，跨设备同步 | 🟢 小 |
| 16 | **多模态** | ❌ 截图保存但模型看不到 | 图片附件/缩放/粘贴、PDF/document blocks | ⚠️ 中 — 缺图片输入 |
| 17 | **其他亮点** | cron 调度器✅、policy limits✅、验证计划执行✅、**Windows 平台意识**（cmd/powershell/GBK）✅ | session replay、文件快照、voice、computer use、IDE 集成、通知 | 各有所长 |

## 优先补齐清单（按 价值/成本 排序）

### 🎯 P0 — 高价值低成本（建议下一批实现，每项 <1 天）

1. **Prompt caching** — Anthropic 用 `cache_control` 缓存 system prompt + 工具定义，OpenAI 用 `prompt_caching`。省 50-80% 重复 token，是成本杠杆。参考 `services/api/claude.ts::getCacheControl()`。
2. **Git 上下文注入** — 在 `_effective_system()` 里注入分支/5条最近提交/status 摘要。纯字符串拼接，模型立刻更懂项目。参考 `context.ts::getGitStatus()`。
3. **精确 token 计数 + 窗口感知** — 用 `tiktoken` 替换启发式估算；压缩阈值按模型上下文窗口动态算，而不是硬编码 100K。
4. **/cost /usage 成本估算** — 加一张价格表（`PROVIDER_PRESETS` 里已有模型清单），按 token 算美元。参考 `utils/modelCost.ts`。
5. **危险命令模式检测** — `bash` 工具前扫 `rm -rf /`、`format`、`git push --force` 等模式。纯规则，无需 LLM。参考 `dangerousPatterns.ts`。
6. **并行子 agent** — Task 工具加 `concurrent` 语义，或 AgentTool 支持同时 spawn 多个。这是「能用」到「好用」的分水岭。

### 🔧 P1 — 中价值（1-3 天）

7. **Hooks 事件扩展** — 加 `stop`、`user_prompt_submit`、`session_start/end`、`subagent_start/stop`。hook 后端抽象已存在，事件是枚举问题。
8. **Memory 相关性选择** — 把 `search_facts` 从关键词改成「标题/描述打分 + 上限5条」的侧查询，或至少加权关键词。参考 `findRelevantMemories.ts`。
9. **图片多模态** — OpenAI 兼容 provider 直接支持 `image_url` content block（DeepSeek/Qwen 都支持）。截图工具已有，差一层传递。
10. **keybindings** — 支持 Ctrl+C/R/L 与自定义绑定，当前 Textual TUI 裸奔。

### 🧭 P2 — 已在 ROADMAP（工程量大，不建议近期）

OS 沙箱、远程执行、team/swarm、完整 TUI、MCP resources/SSE、reactive compact、session replay。

## 差异化优势（保留并深化）

- **6 provider 预设**（zhipu/anthropic/openai/deepseek/kimi/qwen）——Claude Code 没有的国内模型适配
- **Windows 平台意识**——cmd/powershell 双 shell、GBK/UTF-8 编码处理、Playwright 浏览器工具
- **cron 调度器**（1s 轮询 + 持久化）、**policy limits**、**验证计划执行**、**免 API 启动建议**

## 结论

**最值得先做的是 P0 的 1、2、3**——它们不需要新架构，是纯增量，但对「像不像 Claude Code」的体感提升最大：prompt caching（省钱）、git 上下文（变聪明）、精确 token（不爆窗口）。

围绕「国内模型 + Windows」做深度的差异化方向，比逐项追赶 Claude Code 更值。
