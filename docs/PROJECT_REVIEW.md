# OhWangAgent 项目评审报告

> 评审日期：2026-08-01 · 评审基准：`main` @ `33d6dad`（464 测试全绿）
> 评审方式：通读源码 + 全量测试复跑 + 覆盖率实测 + 文档一致性核查
> 结论先行：**架构清晰、工程素养高、测试扎实，是一个高质量的「办公 agent」参考实现**；主要短板在文档数据漂移与少量可维护性细节，均不构成功能性障碍。

---

## 1. 项目事实速览（实测数据）

| 维度 | 数值 | 备注 |
| :--- | :--- | :--- |
| 定位 | 交互式 CLI 办公 agent | 文档撰写/会议纪要/检索/任务管理 + 软件工程 |
| 源码规模 | 70 个 `.py` 文件 / 6,179 行 | `ohwang/` 下 |
| 测试规模 | 46 个 `.py` 文件 / 6,490 行 | 测试代码行数超过源码 |
| 工具数量 | 33 个工具模块（约 31 个注册工具） | `ohwang/tools/` |
| Provider | 6 家预设 | Anthropic / OpenAI / 智谱 / DeepSeek / Kimi / Qwen |
| 测试结果 | **464 passed**（49.99s 复跑） | 全绿 ✅ |
| 覆盖率 | 实测 **91%**（`coverage run --source=ohwang --omit=tui/widgets/*`） | 文档声称 98%，见 §5.2 |
| 提交历史 | 30 commits | 集中在 **2026-08-01 一天内**（16:18→23:17） |
| 依赖 | 6 个直接依赖 | 轻量，`pyproject.toml` |
| 环境 | Python ≥3.10 · Windows 开发 | 显式处理 GBK 控制台乱码 |

---

## 2. 亮点与优点

### 2.1 架构分层干净，且文档与代码高度吻合

五层结构（CLI/REPL → Agent 循环 → Provider → Tool 注册表 → 权限/服务）与
`docs/ARCHITECTURE.md` 的描述一一对应，没有「文档画的架构和代码对不上」的通病。

- **`ohwang/agent.py`**：Agent 循环非常紧凑（162 行），工具执行链
  `hook(pre) → 权限 → policy → 执行 → 统计/后置钩子` 顺序正确、异常兜底完整
  （工具抛异常返回 `is_error` 块而非让循环崩溃，`agent.py:203-217`）。
- **`ohwang/providers/openai_provider.py`**：统一事件流抽象设计得好——OpenAI
  流式增量按 `index` 累积 tool_use（`openai_provider.py:130-175`），
  `include_usage` 正确归账 token，6 家模型零代码接入。
- **`ohwang/tools/base.py`**：`BaseTool` 四要素（name/description/schema/默认权限）
  声明式设计，加一个工具 = 建一个子类 + 注册一行。

### 2.2 测试工程素养突出

- **测试代码（6,490 行）超过源码（6,179 行）**，46 个测试文件覆盖每个子系统。
- `tests/helpers.py` 的 `ScriptedProvider`（重放事件序列）+ `MockSearchProvider`
  让集成测试**无网络、无真实模型**即可确定性复现——这是 agent 项目最难做对的部分。
- 测试覆盖到真实实现细节：cron 星期语义（`py_dow_to_cron`）、浏览器滚动方向、
  Anthropic usage 归账、子 agent 权限隔离、SSRF scheme 拒绝、CJK token 估算等。

### 2.3 有「真实使用反馈循环」

CHANGELOG 记录了多轮真实 DeepSeek 场景实测与高强度使用修复：并发锁、GBK 乱码、
国内 web_search 不可达、编码容错、记忆缓存失效等。**能修出这些问题，说明项目不是
「写出来就完」的玩具，而是被真正用过、被 review 过的。**

### 2.4 功能广度对标 Claude Code

权限四模式+参数级规则、hooks、policyLimits、自动记忆提取、Skill/Plugin/LSP、MCP、
cron 持久化、multi_edit、diff 审批、Task v2、worktree…… 覆盖了 Claude Code 的
大部分能力域，且已实现项都有测试。

### 2.5 安全细节到位

- `web_fetch` 拒绝非 http/https scheme，堵住 `file://` SSRF 向量。
- `deny` 规则优先于 `always` 记忆（先前的短路 bug 已修复）。
- `file_preview_edit`/`multi_edit` 默认只 preview，显式 `apply=true` 才写盘。
- `.env` 与 `.ohwang/` 均被 `.gitignore` 排除且未入库（已核查 `git ls-files`）。

---

## 3. 可维护性 / 代码质量问题

以下问题不构成功能性 bug（已全量复跑 464 测试），但值得后续收敛：

### 3.1 `cli.py` 闭包前向引用（脆弱排序）— 中优先级

`build_agent()`（`cli.py:113`）中 `_run_locked`（:171）引用后文才定义的 `agent`
（:260），`_agent_factory`（:189）引用后文才定义的 `compactor/hooks/policy`
（:251-256）。Python 闭包晚绑定使它能跑，但**一旦有人重排 `agent = Agent(...)`
到 `scheduler.start()` 之后就会在 cron 启动期爆炸**。建议把 `_agent_factory`
改成显式参数注入，或把组件构建顺序前移，消除「按行号祈祷顺序」的隐式依赖。

### 3.2 主/子 agent 共享 Provider 对象 — 低优先级

`_agent_factory` 直接复用主 `provider`。`AnthropicProvider` 内部的 token 累计
（usage）会被子 agent 混入主 agent 统计。当前共享 `UsageTracker` 是设计意图，
但 Provider 级状态建议与主 agent 隔离。

### 3.3 38 处宽泛 `except Exception` — 低优先级

多数是刻意的健壮性兜底（渲染回调、后台任务），但部分吞错无日志。
建议给「真该静默」的路径补 `logger.debug` 或注释说明为什么吞。

### 3.4 自定义 `.env` 加载器 — 低优先级

`cli.py:_load_env` 手写了 python-dotenv 的极简子集（不支持变量展开/多行值），
对当前需求够用，但已有现成依赖可替换时不建议继续扩展。

---

## 4. 测试质量

- **亮点**：ScriptedProvider 测试基座是本项目最值得借鉴的部分；办公场景测试
  （`test_scenarios.py`）把「会议纪要→Todo→文档」串成端到端剧本。
- **待补**：
  - MCP 用真实 stdio fake server 测了 JSON-RPC，但 **Playwright/LSP 仍是 mock 层
    验证**，真实浏览器/语言服务器路径未在 CI 覆盖——可接受，但文档应明示。
  - 未见针对 `cli.build_agent` 整体装配的冒烟测试（大量闭包依赖正是靠测试
    未覆盖才遗留了 3.1 的脆弱性）。建议加一个「build_agent 不抛错 + cron 后台
    触发不炸」的装配测试。

---

## 5. 文档一致性核查（本轮实测发现的不一致）

### 5.1 版本号漂移

| 文件 | 声称 | 实际 |
| :--- | :--- | :--- |
| `pyproject.toml` | `version = "0.2.0"`，描述 "coding agent" | 与文档 v0.3.0 不一致 |
| `ARCHITECTURE.md` / `ROADMAP.md` | `v0.3.0` | 与 pyproject 不一致 |

建议：统一 `pyproject.toml` 版本为 v0.3.0，并把描述改为
「office agent」（当前仍写 "coding agent"，与定位不符）。

### 5.2 测试规模与覆盖率声明过期

| 位置 | 声明 | 本轮实测 |
| :--- | :--- | :--- |
| `README.md:97` | "222 unit tests" | 实际 464 |
| `ROADMAP.md` 首部 | "222 测试全绿，88 个 Python 文件" | 实际 464 测试 / 70 源码文件 |
| `ARCHITECTURE.md` 首部 | "覆盖率 98%" | 实测 91%（`--source=ohwang --omit=tui/widgets/*`） |

测试数声明过期最容易被误读成「项目只有一半测试」。建议每批完成后用
`grep -c` 跑一遍数字回填，或把测试数改为从 CI 自动生成。

### 5.3 说明

98% 与 91% 的差异可能与当时测量命令（是否含 `--source`、omit 范围）有关，
但按当前仓库复现，`coverage run --source=ohwang -m pytest` 得到的是 91%。
91% 本身已是优秀水平，建议在文档中改标实测值并注明测量命令，避免误读。

---

## 6. 安全与健壮性总评

- **权限模型**：四模式 + `.ohwang/settings.json` 规则 + always 记忆，规则优先级
  deny > allow > ask > 默认，`deny` 优先于 `always` 的修复很关键（防「先放行后
  拉黑」绕过）。
- **进程/并发**：REPL 前台与 cron 后台共用同一把 `run_lock`，杜绝并发 `run()`
  污染 `messages`——这是 agent 类项目最容易踩的隐性 bug，已正确处理。
- **编码**：Windows 下 `SetConsoleOutputCP(65001)` + 流式 stdin 字节级 UTF-8/GBK
  容错，中文办公场景的刚需，处理到位。
- **密钥**：`.env` 含真实 DeepSeek key 但已 gitignore。**建议**：若后续要公开
  仓库到不信任的 remote，先轮换该 key。

---

## 7. 对「对标 Claude Code」定位的客观评估

- 从 ROADMAP 看，项目已逐模块核对 Claude Code v2.1.88 能力域并诚实标注
  ✅/❌/⚠️，没有夸大（如明确标注 MCP resource 缺失、IDE bridge 归 P4）。
- **已对齐**：Agent 循环、权限、hook、policy、记忆、skill/plugin/lsp、cron、
  worktree、multi_edit、diff 审批、task v2、自动记忆提取。
- **真实差距**：MCP resource、NotebookEdit、命令历史/补全、沙箱/网络控制、
  IDE bridge、OAuth、遥测、remote/server——均已归 P4「按需」，定位克制。
- 结论：**「对标」不是「复刻」**，ROADMAP 的差距矩阵是诚实且有办公价值排序的。

---

## 8. 风险与建议（按优先级）

| # | 建议 | 优先级 | 依据 |
| :--- | :--- | :--- | :--- |
| 1 | 统一版本号到 v0.3.0，改 pyproject 描述 | 低，立即可做 | §5.1 |
| 2 | 回填 README/ROADMAP 测试数与文件数，修正覆盖率声明 | 低，立即可做 | §5.2 |
| 3 | 重构 `_agent_factory`/`_run_locked` 前向引用为显式注入 | 中 | §3.1 |
| 4 | 增加 `build_agent` 装配冒烟测试（含 cron 后台触发） | 中 | §4 |
| 5 | 子 agent 使用独立 provider 或隔离 provider usage 状态 | 低 | §3.2 |
| 6 | 为 38 处宽泛 except 补齐日志/注释 | 低 | §3.3 |
| 7 | 公开前轮换 `.env` 中的 key | 安全 | §6 |

---

## 9. 综合评分

| 维度 | 评分 | 说明 |
| :--- | :---: | :--- |
| 架构设计 | ★★★★★ | 分层清晰、抽象合理、文档与代码吻合 |
| 代码质量 | ★★★★☆ | 整洁、有注释；闭包前向引用等 1-2 处脆弱点 |
| 测试 | ★★★★★ | 测试/源码比>1，无网络确定性集成测试基座是亮点 |
| 文档 | ★★★★☆ | 体系完整（README/ARCH/CHANGELOG/ROADMAP/AGENTS）；数据有漂移 |
| 功能广度 | ★★★★☆ | 对标 Claude Code 覆盖广；MCP resource 等按 P4 挂起是诚实取舍 |
| 健壮性 | ★★★★☆ | 并发/编码/安全细节到位；浏览器/LSP 仅 mock 验证 |

**总体：4.5/5** —— 在一个工作日内从 MVP 推进到 464 测试全绿、架构对标 Claude Code
的办公 agent，工程质量显著高于一般教育项目平均水平。核心价值在**架构范本**与
**测试基座**（ScriptedProvider）；主要债务是文档数据漂移与个别可维护性细节，
均不影响当前功能。

> 注：本评审基于 2026-08-01 `main@33d6dad` 快照，未接入真实模型做端到端验证
> （测试均为 mock provider 路径）。
