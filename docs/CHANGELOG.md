# OhWangAgent 变更日志

> 按日期倒序记录开发进度、问题修复与办公场景验证。
> 测试规模演进：180 → 212 → 222 → 224 → 232 → 239 → 244（全绿）。

---

## 2026-08-01

### 代码审查（本轮）

| 提交 | 内容 |
| :--- | :--- |
| — | **全量代码检视**：通读 `ohwang/` 全部 60+ 文件，修复以下问题 |
| — | **TUI bug 修复**：`tui/widgets/app.py` 全部 8 处引用未定义的 `ChatLog`（类实际叫 `ChatPanel`），TUI 启动即 NameError；已替换为 `ChatPanel`，并新增 AST 测试防止回退 |
| — | **glob 一致性**：`glob` 工具此前不跳过忽略目录（`grep` 有 `_SKIP_DIRS`），`**/*.py` 会扫入 `.venv`/`node_modules`；现与 grep 共用同一组忽略目录，并支持前缀定位 |
| — | **MemoryStore 缓存**：agent 每轮迭代调用 `_effective_system()` → `render_context()` 每次都读盘（facts.json + CLAUDE.md）；现按 mtime 缓存 facts，写操作显式失效，避免重复磁盘 IO |
| — | **资源清理**：`BrowserSession.close()` 现在也停掉 Playwright 实例（`_pw.stop()`）；`services/__init__` 补导出 `load_lsp_tools`（与 `load_mcp_tools` 对齐） |
| — | **性能/健壮性**：`file_read` 用 `itertools.islice` 按需读取避免全量载入；`SessionStore.save` 改为存在性探测避免同秒保存覆盖 |

### 测试

244 个测试全绿（本轮 +5：glob 忽略目录、memory 缓存失效/mtime 命中、session 秒内唯一 ID、TUI AST 无未定义引用）。

---

### 功能开发

| 提交 | 内容 |
| :--- | :--- |
| `66357ec` | **P1 记忆系统接线**：`MemoryReadTool`/`MemoryWriteTool` 此前有实现+测试但从未注册，且 facts 只写不读。修复：`default_tools()` 新增 `memory_store` 参数注册两个工具；`Agent._effective_system()` 将 `render_context()`（CLAUDE.md/AGENTS.md + facts）注入 system prompt；cli 注入主 agent / 子 agent factory / tools |
| `66357ec` | **P2 LSP 接线**：`LSPClient`+`LSPDiagnoseTool` 此前为死代码。新增 `load_lsp_tools()`（仿 MCP 读取 `.ohwang/lsp.json`，支持 `{"command":...}` 与 `{"servers":{...}}` 两种格式），cli 在 `lsp` 特性开启时加载；`lsp_diagnose` 工具由此可被模型使用 |
| — | **P3 Scheduler 修复**：`add()` 此前在表达式恰好匹配当前分钟时跳过校验，垃圾字段还会在 `cron_matches` 直接抛 `ValueError`；改为始终先校验、安全返回 False。`stop()` 现会 join 工作线程并清空引用 |
| — | **P5 去重**：`BashTool`/`PowerShellTool` 的 `_truncate` 与 stdout/stderr 合并逻辑抽到 `tools/shell_output.py`（`truncate` + `command_result`），两个工具共用 |
| — | **项目约定**：新增根目录 `AGENTS.md`，固化「每次优化须补齐测试 / 文档 / 提交」的开发流程，并会被 `MemoryStore` 自动加载为 agent 上下文 |

### 测试

239 个测试全绿（本轮 +7：scheduler stop/join、始终校验、垃圾字段不抛异常、`command_result` 成功/非零/超时）。

---

### 功能开发

| 提交 | 内容 |
| :--- | :--- |
| `c1c69fd` | **P3-A / P3-B 完成**：自动记忆提取（`MemoryExtractor`，会话增长≥10 条自动提炼事实入库）、hooks 系统（`HookManager`，pre/post tool + notif，`.ohwang/hooks.json` 命令钩子）、策略上限（`PolicyLimits`，`.ohwang/policy.json`）、使用统计（`UsageTracker`，`/summary` 命令）、`config` / `sleep` 工具 |
| `9b95c37` | **P3-C 完成**：`synthetic_output`（展示文本不进模型上下文）、`brief`（会话进度简报）、`snip`（保存输出片段到 `.ohwang/snips/`）三个工具，接线 agent + CLI |

### 文档

| 提交 | 内容 |
| :--- | :--- |
| `f76e1ca` | 新增 `docs/ARCHITECTURE.md`（模块图、Agent 循环、权限/钩子/策略/记忆/调度机制、扩展点、数据目录、已知缺口）；README 增加入口链接并修正测试数 |
| — | `docs/ROADMAP.md` 标记 P3-A/P3-B/P3-C 为 ✅，工具盘点 24→27 |

### 问题修复（办公日模拟中发现）

| 提交 | 问题 | 修复 |
| :--- | :--- | :--- |
| `c1c69fd` | Windows 控制台中文乱码 | `setup_utf8()`：`SetConsoleOutputCP(65001)` + stdout/stderr 强制 UTF-8 |
| `2146581` | openai/anthropic SDK 默认超时 10 分钟，慢网络假死 | `timeout=60` + `max_retries=2`，网络错误包装为友好信息 |
| `2146581` | DuckDuckGo 不可达时 `web_search` 静默返回空，agent 盲目重试 | `SearchError` 异常，`web_search` 明确报 FAIL，agent 自动改用 `web_fetch` 兜底 |
| `2146581` | 管道/脚本输入被按 GBK 解码，产生孤立代理项导致 API 报错 | `setup_utf8()` 增加 stdin 重配置为 UTF-8 + `SetConsoleCP(65001)` |

### 办公日场景验证（真实 DeepSeek 模型）

| 场景 | 结果 |
| :--- | :--- |
| 晨会转录 → 正式会议纪要 | ✅ 自动生成 9 项带负责人/截止日期的待办清单 |
| 销售数据分析 → 周销售简报 | ✅ 自动写脚本计算渠道占比/退款率并成文 |
| 网络调研 → 摘要 | ✅ web_search 失败后自动改用必应抓取，产出 130 字摘要 |
| todo 驱动多步周报 | ✅ 建清单→逐步执行→更新状态→成文 |
| REPL `/summary` `/save` `/resume` | ✅ 会话保存与恢复、使用统计正常 |

### 测试

224 个测试全绿（本轮 +44：记忆提取、hooks、策略/摘要、config/sleep、输出工具、agent 集成、搜索容错）。

---

## 2026-07-31（历史）

- `f1dd62b` MVP → `29114c6` P0（压缩/todo/plan/会话）→ `d58077d` P1+P2（web/skill/plugin/lsp/memory/flags/TUI）
- `63f730f` P1 接线 + 权限规则 + UTF-8 控制台
- `00310af` P3 工具批（powershell/tool_search/worktree/cron/browser）+ DeepSeek v4 Provider
- `433b371` +50 单测与办公场景测试（180 全绿）；修复 provider schema 与 plan-mode 还原；办公 agent 定位
