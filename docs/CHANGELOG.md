# OhWangAgent 变更日志

> 按日期倒序记录开发进度、问题修复与办公场景验证。
> 测试规模演进：180 → 212 → 222 → 224 → 232 → 239 → 244 → 250 → 371 → 387 → 390 → 395 → 404 → 410 → 412 → 420 → 432 → 450 → 464（全绿）。

---

## 2026-08-01

### 代码审查修复批次：并发锁 / 权限安全 / 健壮性

全量通读 `ohwang/` 60+ 文件后的审查修复，分三个提交落地（`4fc16c9` `ed10401` `630e5b0`）：

| 提交 | 内容 |
| :--- | :--- |
| `4fc16c9` | **并发/调度/浏览器/Anthropic 用量**：`cli.build_agent` 与 REPL 共用同一把 `run_lock`（此前两个独立 Lock 使 cron 后台与 REPL 前台可并发 `agent.run()` 污染 `messages` 状态）；`scheduler.start()` 移到 `agent` 绑定之后，消除启动期 NameError 窗口；cron 星期字段改为按 cron 语义（0=Sun）匹配（此前直接比较 Python `tm_wday`(0=Mon)，`* * * * 1` 在周二触发），新增 `py_dow_to_cron`；`browser.scroll` 方向修正（up 负增量）；`AnthropicProvider` 捕获 `message_start`/`message_delta` 的 usage，`/summary` 对 Anthropic 不再显示零 |
| `ed10401` | **权限/安全**：子 agent 使用独立 AUTO `PermissionManager`（此前与主 agent 共享，子 agent 的 plan_mode/config 工具会篡改主 agent 权限状态），并继承 policy/compactor/usage/hooks 防失控；`deny` 规则优先于 `always` 记忆（此前 always 短路先于 deny）；`file_preview_edit`/`multi_edit` 仅显式 `apply=true` 才写盘（`preview:false` 不再隐含写入）；`web_fetch` 仅允许 http/https scheme（拒绝 `file://` 等 SSRF 向量）；`agent` 对缺 name/id 的畸形 provider 事件不再 KeyError 崩溃，渲染回调异常写 stderr |
| `630e5b0` | **健壮性**：`grep` `errors=ignore`→`replace`（非法 UTF-8 字节不再静默丢弃）；`MemoryStore.render_context` 缓存按（项目文件签名+facts 签名）失效，CLAUDE.md 变更后不返回陈旧上下文；`maybe_extract` 在 provider 调用失败时不推进计数（瞬时网络错误不再导致整场跳过记忆提取）；`_load_env` 只剥离首尾配对的一对引号；token 估算对 CJK 按 ~1 字符/token（中文 prompt 不再被严重低估） |

### 测试

464 个测试全绿（本轮 +14：py_dow_to_cron、cron 语义星期、浏览器滚动方向、Anthropic usage、共享 run_lock、子 agent 权限隔离、deny 优先于 always、preview:false 不写盘、web_fetch scheme 拒绝、grep 非法字节保留、render_context 失效、maybe_extract 失败不推进、.env 配对引号、CJK token 估算）。

### Claude Code 对比补齐：MultiEdit / Diff 审批 / Cron 持久化

按 Claude Code 系统对比（已写入 ROADMAP 第 5 节）补齐第一梯队缺失模块：

| 提交 | 内容 |
| :--- | :--- |
| — | **MultiEdit 多文件编辑**：`multi_edit` 工具一次调用批量替换多文件，preview/apply 双模式，歧义/缺失/空 old_string 安全跳过 |
| — | **Diff 查看/应用**：`file_diff`（纯预览）+ `file_preview_edit`（预览→审批→应用，默认 ask 权限）；unified diff 用标准库 difflib，无第三方依赖 |
| — | **定时任务持久化**：`Scheduler` 增 `state_file`，cron 存 `.ohwang/cron.json`（utf-8-sig 加载/写保存），add/remove 即时落盘，重启不丢 |
| — | **系统对比**：ROADMAP 新增"Claude Code 系统对比"章节（已对齐/已补齐/待补/平台化四类），排除早期误判项 |
| — | 端到端验证：cron 重启保留；file_preview_edit 预览 diff 防截断（agent 主动发现风险）；multi_edit 预览发现字面替换会误伤已有词 |

### 测试

450 个测试全绿（本轮 +18：cron 持久化/BOM/坏状态/remove 持久化、file_diff 预览/无差异、preview_edit 默认不写/apply、multi_edit 预览/应用/跳过/歧义/replace_all）。

### 功能补充：Task v2 + VerifyPlanExecution（P3-D 完成）

补齐 ROADMAP P3-D 任务与协作增强，办公多任务管理能力：

| 提交 | 内容 |
| :--- | :--- |
| — | **Task v2 结构化任务**：`TaskStore` 持久化到 `.ohwang/tasks/*.json`（id/标题/描述/状态/父任务/输出/时间戳）；6 个工具 `task_create`/`task_get`/`task_update`/`task_list`/`task_stop`/`task_output`，覆盖 Create/Get/Update/List/Stop/Output 全 CRUD；区别于扁平 todo 列表，任务带输出捕获与跨会话持久化 |
| — | **VerifyPlanExecutionTool**：计划执行后按步骤校验（done/partial/missed + evidence），输出结构化校验报告；有 missed 步骤时标记 error，防止模型过早宣称成功 |
| — | CLI 创建 `TaskStore` 并接入主 agent 与子 agent 工具链 |
| — | 端到端验证：Task v2 完整工作流（创建3任务→更新→列表→完成+输出）落盘确认；VerifyPlan 两步计划校验 2/2 done |
| — | workflow_scripts 评估后跳过（低价值，记为后续项） |

### 测试

432 个测试全绿（本轮 +12：TaskStore CRUD/持久化/状态过滤/非法状态忽略、task 工具链、verify_plan 各状态/空/模式）。

### 功能补充：SendUserFile / PromptSuggestion + 修复命令 BOM bug

补齐 ROADMAP 中 P3 缺口，新增两个办公场景高价值功能：

| 提交 | 内容 |
| :--- | :--- |
| — | **SendUserFileTool**：生成文件后交付给用户——在终端展示文件内容（带文件名/字数标题栏、2000 字符截断），内容不塞入模型上下文（省 token），配合 file_write 形成"生成→交付"闭环；复用 display_callback |
| — | **PromptSuggestion**：新会话启动时基于工作区状态（待办/资料文件/项目记忆）规则生成最多 3 条建议，零额外 API 调用；用户告别"空白开始" |
| — | **修复 `read_stdin_line` UTF-8 BOM**：管道输入文件带 BOM（`[IO.File]::WriteAllText` UTF8 默认写入）时，解码后残留 `\ufeff` 导致 `/exit` 等命令匹配失败、被误发给模型；现解码后剥掉 BOM |
| — | 端到端验证：file_write 生成日程表 → send_user_file 终端展示；新会话启动显示建议 |

### 测试

420 个测试全绿（本轮 +8：SendUserFile 展示/截断/缺失/BOM、suggest_prompts 文件/待办/空目录、read_stdin_line BOM）。

### Token 消耗实测 + usage 统计能力

| 提交 | 内容 |
| :--- | :--- |
| — | **API token 统计**：`BaseProvider` 增 `usage_prompt_tokens`/`usage_completion_tokens`/`usage_calls` + `_record_usage`/`usage_report`；`OpenAIProvider` 流式启用 `stream_options.include_usage`，从 API 精确获取每轮 prompt/completion tokens（deepseek 验证有效） |
| — | **`/summary` 显示 token**：新增 "Tokens: N total (X in / Y out, Z calls)" 行，用户可实时查看会话消耗 |
| — | **办公场景实测**（发布会要点简报，12 轮迭代/24 消息/3 次 API）：总 **74348 tokens**（prompt 71193 96% + completion 3155）；prompt 大头是 agentic 循环每轮重发消息历史 + system/tools 固定开销 |
| — | **优化收益量化**：每轮迭代固定重复开销 = system(236) + 记忆(348) + tools(1910) ≈ 2494 tokens；12 轮迭代优化前 29928 → 优化后 2494，**节省约 27434 tokens/场景（重复开销降 92%，占场景总 token 的 37%）** |

### 测试

412 个测试全绿（本轮 +2：provider usage 累积、openai provider 从流式 chunk 记录 usage）。

### Token 消耗优化（降低 API 成本）

| 提交 | 内容 |
| :--- | :--- |
| — | **system prompt 缓存**：`Agent._effective_system()` 原本每次迭代重建（todo render + 记忆渲染 + 字符串拼接），现单次 run 内缓存复用，仅工具执行后/下次 run 失效；`render_context` 实测从"每迭代多次"降为"单次 run 1 次" |
| — | **工具 specs 缓存**：`ToolRegistry.specs()` 原本每次迭代全量序列化 20 个工具（约 1910 token），现注册后缓存、register 时失效；单次 run 内 `to_spec` 只调用工具数次（20），不再随迭代次数翻倍 |
| — | **记忆上下文缓存**：`MemoryStore.load_project_context()` 按 CLAUDE.md/AGENTS.md 的 mtime+size 签名缓存；`render_context()` 整体缓存，facts 写操作（add/delete/import）自动失效 |
| — | **facts 注入上限**：system prompt 记忆段最多注入最近 30 条 facts（超出提示用 memory_read 检索），防止长期使用后记忆段无限膨胀 |
| — | 实测验证：多轮工具调用场景（文件读取→综合→写入→读回）优化后功能正常，`to_spec`/`render_context` 调用次数显著下降 |

### 测试

410 个测试全绿（本轮 +6：registry specs 缓存/失效、agent system 缓存、memory render_context 缓存与失效、project context 缓存、facts 上限截断）。

### 高强度办公场景第三轮：修复国内搜索不可达短板

模拟"产品经理准备发布会"高强度一天（多源资料综合报告、长任务链错误恢复、并行多任务+记忆沉淀、跨会话记忆回归），全部通过。发现并修复核心短板：

| 提交 | 内容 |
| :--- | :--- |
| — | **国内 web_search 不可达**：默认 provider 是 DDG（html.duckduckgo.com 被墙，国内必超时），办公"资料检索"核心能力失效。新增 **`BingSearch` provider**（`cn.bing.com/search`，无需 API key，国内可达，已验证 200/10 结果）；`make_search_provider` 默认改为 Tavily(有key)→**Bing**→DDG 回退 |
| — | **WebSearchTool 回退链**：主 provider 抛 SearchError 时自动尝试备选（Bing↔DDG），全部失败才报错并汇总各 provider 原因；`default_tools` 组装 Bing 主 + DDG 备 |
| — | 端到端验证：真实模型多轮搜索（中英关键词）、筛选相关结果、给出行业报告渠道建议；`Auto-saved 6 memory fact(s)` 记忆自动提取触发 |

### 测试

404 个测试全绿（本轮 +9：Bing 解析/HTTP错误/网络错误/空结果、make_search_provider 默认 Bing、WebSearchTool 回退/全失败汇总）。

### 流式输出全局优化

| 提交 | 内容 |
| :--- | :--- |
| — | **真流式**：`Renderer.stream_text` 原只累积、回合结束才一次性 flush（无流式效果）；改为按块即时输出 |
| — | **智能 flush**：小 chunk 累积到 128 字符 / 50ms 时间间隔 / 句子结束符才写盘，减少高频 write 调用同时保持流畅 |
| — | **工具调用分隔**：`tool_call` 前若文本未换行自动补 `\n`，避免工具行与思考文本粘连 |
| — | **回调异常保护**：agent 层 `on_text`/`on_tool_call`/`on_tool_result` 捕获异常，渲染问题不再中断整个模型流 |
| — | 实测：8 chunk 在 0~1.06s 逐段输出、内容无损；真实 deepseek 中文流式完整 |

### 测试

395 个测试全绿（本轮 +5：流式缓冲/句子 flush/大块 flush/tool_call 补换行/end_turn flush）。

### 办公场景第二轮：跨会话记忆/子agent/真实网络/管道编码

模拟"产品经理推进客户管理系统升级项目"多日工作流，验证之前未覆盖的功能，修复管道中文编码 bug：

| 提交 | 内容 |
| :--- | :--- |
| — | **REPL 管道中文输入乱码**：PowerShell 管道以系统代码页(GBK)编码，Python stdin 按 UTF-8 解码导致中文变 `?`，模型收到乱码、任务卡死。新增 `read_stdin_line()`：TTY 用交互输入，管道用 `sys.stdin.buffer` 读字节 + UTF-8 优先/含 `\ufffd` 时回退 locale 解码；`setup_utf8` 不再强制改 stdin 编码 |
| — | 真实场景验证通过：`chcp 65001` UTF-8 管道中文 prompt 完整到达模型 |

### 第二轮办公场景验证记录（deepseek-v4-flash）

- ✅ **记忆跨会话持久化**：memory_write 3 条决策 → 新进程自动 memory_read 检索并应用（含"预算超支"提醒）
- ✅ **子 agent 委派**：独立分析 Q2 销售 CSV → 区域汇总/占比/合计校验全部正确（华东37.38%/华北31.78%/华南30.84%）
- ✅ **真实网络抓取**：web_fetch python.org 首页 → 准确提炼导航结构与主推内容
- ✅ **记忆+工具+推理协同**：读技术选型草案 + 预算记忆(80万) → 三方案成本估算/预算符合性分析 → 落盘对比报告
- ⚠️ PowerShell 5.1 原生管道传中文给 native 程序在语言层已损坏为 `?`（Python 侧无法恢复），用 `cmd /c chcp 65001` 或 PowerShell 7 规避

### 测试

390 个测试全绿（本轮 +3：read_stdin_line UTF-8/GBK 字节解码、EOF）。

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
