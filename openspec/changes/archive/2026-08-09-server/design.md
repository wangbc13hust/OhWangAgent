## Context

Agent 核心已经是「渲染器无关」的：`Agent.run(user_input, on_text, on_tool_call,
on_tool_result, on_compact, on_turn) -> final_text` 是同步函数，五个回调吐出过程
事件。`cli.py` 现在把这些回调绑到 TTY 渲染器，并让 REPL 前台与 cron 都经过同一把
`threading.Lock`（`run_lock`，经 `build_agent(args, run_lock)` 下发）。one-shot 路径
`_run_once` 的固定顺序是：`with run_lock: agent.run(...)` → `renderer.end_turn()` →
`memory_extractor.maybe_extract(...)`。`SessionStore.save(messages, preview) -> sid` /
`load(sid) -> list[dict] | None` 已由 `test_scenario_save_resume` 验证。动机见
proposal.md - Why。

## Goals / Non-Goals

**Goals:**
- `ohwang serve` 启动 localhost 守护进程，经 HTTP 提供 agent。
- REST（`/run`）与流式（SSE）传输，把五个回调绑成 wire 事件；**零新增三方依赖**。
- 与 REPL、cron 共享现有 `run_lock` 的单飞执行。
- 会话续传复用 `SessionStore`。

**Non-Goals:**
- 不做 WebSocket——server→client 主动推送（通知中心）是后续 change；聊天前端只需要
  单向流式，SSE 已覆盖。
- 不做鉴权 / TLS / 多用户。
- 本 change 不含 Web UI 页面本身，只提供前端可依赖的传输层。

## Decisions

- **D1 — 传输层：stdlib `ThreadingHTTPServer` + SSE，零新依赖。** agent 循环是同步
  的，异步服务器不带来收益。SSE 就是普通 HTTP 分块文本：请求线程可直接内联跑
  `agent.run`，把事件写进未关闭的响应——无需 async、无 WS 握手、无消息队列。聊天
  前端只需要 server→client 单向流式，SSE 够用；WebSocket 留给真正需要 server 主动
  推送的通知功能。备选：aiohttp/WebSocket（加依赖，且要为同步循环搭 async 桥）、
  FastAPI+uvicorn（对本项目过重）。

- **D2 — 并发：线程 + 复用现有单飞 `run_lock`。** `ThreadingHTTPServer` 每连接一线程。
  `/run` 与 `/stream` 拿 REPL 和 `scheduler._runner` 已在用的同一把 `run_lock`，三路
  在同一把锁上串行，不新增并发机制。`/health` 不拿锁，长 run 期间保持可响应。run 在
  请求线程内内联执行（持有锁），SSE writer 由与终端渲染器相同的回调喂入。备选：工人
  队列 / async executor——不需要，因为锁已经串行，内联还保证事件同步。

- **D3 — 会话：复用 `SessionStore`，对齐 `test_scenario_save_resume`。** 请求体带
  `message` + 可选 `session_id`。无 id：在空 `agent.messages` 上跑，结束后 save 并返回
  新 id。有 id：run 前 `agent.messages = store.load(sid)`，run 后 save。流式模式下
  `done` 事件携带 session_id。

- **D4 — 命令形态：** `ohwang serve --host 127.0.0.1 --port <n>`（默认 host
  127.0.0.1，默认端口避开常见开发端口）。SIGINT/SIGTERM 优雅退出：停止接收新连接、
  让在跑的 run 在锁内跑完、释放端口。`serve` 复用 `build_agent(args, run_lock)`，daemon
  拿到与 CLI 相同的组装结果（agent / scheduler / memory_extractor）；TTY 渲染器不使用，
  服务端回调绑 SSE。

- **D5 — 与 CLI 共享 run 后置流程：** run 后镜像 `_run_once`：`memory_extractor.maybe_extract`
  （失败静默），再 `session_store.save(...)`（对话必须持久化，这是 server 新增的一步）。
  异常时向 SSE 发 `error` 事件并返回 5xx，而不是崩进程。仅渲染回调不同；server 路径
  永不触发 isatty 门控的反馈。

## Risks / Trade-offs

- 长 run 持有 `run_lock`，第二个 `/run` 会排队、`/stream` 开始前无流式。→ 个人单用户
  daemon 可接受；`/health` 保持可响应。多会话并发是明确的 Non-Goal。
- SSE 于 `ThreadingHTTPServer`：对同一响应的写必须来自同一线程（正是请求线程）。→
  所有写入只发生在 run 回调内，绝不在别的线程写。
- daemon 运行期间 cron 照常执行，但产物暂无收件箱，被丢弃/写日志。→ 接受；通知中心
  （后续 change）成为它们的去处。
- 三路共享 `agent.messages`，忘拿锁就并发改会损坏状态。→ run 入口收敛到一个总是持锁
  的 helper。
- 交互工具（ask_user_question、plan-mode 审批）在 server 模式没有终端。→ 现有
  「非交互 stdin 默认拒绝」行为天然兜底：server 模式下安全地返回不可用；web 审批卡片
  是后续 change。
