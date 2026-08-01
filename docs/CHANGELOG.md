# OhWangAgent 变更日志

> 按日期倒序记录开发进度、问题修复与办公场景验证。
> 测试规模演进：180 → 212 → 222 → 224 → 232 → 239 → 244 → 250 → 371 → 387（全绿）。

---

## 2026-08-01

### 高强度真实使用评测 + 高优先级 bug 修复（真实 deepseek 模型端到端）

以"办公白领的一天"为场景，用真实 `deepseek-v4-flash` 模型跑完整工作流（收件箱→回复邮件、季度汇报 PPT 大纲、营收数据分析、周会行动项、cron 定时提醒、会话保存/恢复），全链路打通。过程中发现并修复 6 个高优先级 bug：

| 提交 | 内容 |
| :--- | :--- |
| — | **CLI 启动崩溃**：`main()` 解包 7 值但 `build_agent` 返回 8 个（skill 轮新增 `skill_loader` 后漏改），启动即 `ValueError`；已对齐 |
| — | **`/help` 触发 rich MarkupError 崩溃**：help 文本含 `[/cron ...]` 方括号被 rich 当 markup 解析；render 层 `info`/`warn`/`tool_call`/`ask` 统一 `rich.markup.escape` 转义用户内容 |
| — | **`/skills` 永远显示 disabled**：`skill_loader` 未传给 `repl`；已接线 |
| — | **`/cron` 引号解析错误**：`split(maxsplit=2)` 拆坏含空格表达式；改用 `shlex.split` |
| — | **hook 命令在错误目录执行**：`_run_cmd` 未传 `cwd`，副作用落到进程启动目录而非 workdir；已传 `cwd=workdir` |
| — | **JSON 配置不兼容 UTF-8 BOM**：settings/flags/hooks/mcp/lsp/policy/session/facts/worktree/skill/plugin 全部读 `utf-8`，Windows 记事本/PowerShell 保存的 BOM 文件被静默忽略；统一改 `utf-8-sig` |

### 办公场景评测补充修复

| 提交 | 内容 |
| :--- | :--- |
| — | **bash/powershell 中文输出崩溃**：`text=True` 按 GBK 解码 UTF-8 字节抛 `UnicodeDecodeError`；新增 `decode_output()` 先 UTF-8 后 locale 容错回退 |
| — | **非交互/管道场景权限问询崩溃**：stdin 为管道时 `Prompt.ask` 抛 `EOFError` 中断任务（实测回复草稿因此丢失）；捕获 EOFError 降级 deny/option-1 |
| — | **`.env` 自动加载**：新增 `_load_env()`（workdir→项目根回退，不覆盖已有环境变量），`--provider deepseek` 开箱即用，无第三方依赖 |

### 测试

387 个测试全绿（本轮 +16：`.env` 加载、decode_output 容错、render EOF 降级、render markup 转义、hooks cwd/BOM、settings BOM）。

### 真实办公场景验证记录（deepseek-v4-flash）

- ✅ 客户邮件起草：读 2 封邮件 → 专业回复 → file_write 落盘 → todo 更新
- ✅ 季度汇报 PPT 大纲：9 页结构化，融合周会纪要项目数据，带待填占位符
- ✅ 营收数据分析：建 CSV → Python 计算 → 数字全部正确（总 583 万/月均 97.2/6 月最大）→ 业务洞察
- ✅ 周会行动项：提炼 4 条（负责人/截止日），诚实标注推断部分
- ✅ cron 调度：cron_create + cron_list 真实可用
- ✅ 会话持久化：`/save` → `/resume` 完整闭环（2 条消息恢复）

### 全量单元测试补齐（覆盖率 82% → 98%）

| 提交 | 内容 |
| :--- | :--- |
| — | **Tier 1（低覆盖模块）**：`mcp.py` 33%→95%（stdio JSON-RPC 全握手：initialize/tools/list/tools/call、超时、坏行、env 合并、load_mcp_tools 成功/失败路径）；`browser.py` 42%→95%（fake Playwright 驱动全部 7 个 action、DOM 截断、截图、close 停实例）；`openai_provider.py` 49%→100%（流式 text/tool_call 累积、坏 JSON、错误包装）；`providers/__init__` 43%→100%（create_provider 各 provider/base_url/未知）；`lsp.py` 47%→93%（LSPClient 生命周期、_rpc_call/_rpc_notify framing、diagnose 解析、load_lsp_tools 各格式） |
| — | **Tier 2**：`search.py` 60%→98%（DDG HTML 解析/unwrap/Tavily/错误）、`plugins/loader.py` 70%→100%（entry_point 激活/失败/返回工具名）、`web_browser.py` 71%→94%（全 action dispatch）、`hooks.py` 81%→96%（cmd glob 过滤、post/notif 不阻塞、handler 异常、_run_cmd 失败） |
| — | **Tier 3（新增 test_gaps.py 补齐分支）**：file_edit 读写 OSError、file_read/file_write OSError、glob 前缀目录/非递归、grep 200 行截断/不可读文件、session 坏文件跳过、tokens 字符串 content、worktree 超时/git 失败、compact _serialize 分支/空摘要、memory 工具全分支、mode label、registry 迭代/空名、scheduler a-b/step、policy 坏 JSON、settings 未知 action、skills frontmatter 标量/缺闭合/坏文件、default_tools skill/web_browser 条件注册 |
| — | **真实子进程交互**：MCP 用 `sys.executable -c` fake stdio server 测完整握手；LSP RPC framing 用 fake proc 测 read/write 失败分支（Windows 文本模式 subprocess 与字节计数不兼容，LSP 改用 monkeypatch 测逻辑） |

### 测试

371 个测试全绿（本轮 +121，覆盖率 82% → 98%，覆盖全部 60+ 模块；剩余缺口为真实浏览器/真实 LSP server 等难以模拟路径）。

### Skill 系统建设（P4，Claude Code 风格）

| 提交 | 内容 |
| :--- | :--- |
| — | **Skill 从死代码到系统级能力**：`SkillTool`/`SkillLoader` 此前有实现但从未注册。现已接线：`default_tools(skill_loader=...)` 注册 `skill` 工具；cli 创建 `SkillLoader` 并加载；`/skills` 命令列出可用 skill |
| — | **SKILL.md 目录格式**：bundled skills 从 `<name>.json` 迁移为 `<name>/SKILL.md`（YAML frontmatter：`name`/`description`/`allowed-tools` + markdown 指令），对齐 Claude Code 规范；`SkillLoader` 内建轻量 frontmatter 解析器（标量/行内列表/块序列，无需 PyYAML） |
| — | **JSON 兼容保留**：`.ohwang/skills/<name>.json` 仍受支持；用户自定义新增 `<name>/SKILL.md` 目录格式；用户 skill 同名覆盖 bundled |
| — | **系统提示注入**：`build_system_prompt(workdir, skills=...)` 新增 skills 段；cli 将 `describe_all()`（`- name: description` 列表）注入 system prompt，agent 依据描述自动决定何时调用 skill |

### 测试

250 个测试全绿（本轮 +6：frontmatter 解析/缺失、SKILL.md 用户 skill 加载、describe_all、系统提示注入/无 skills）。

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
