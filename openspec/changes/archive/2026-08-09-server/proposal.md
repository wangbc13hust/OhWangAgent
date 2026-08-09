## Why

OhWangAgent 目前是纯 CLI 的单机办公 agent——人叫它才动（pull），没有常驻进程。
用户要把它做成**个人办公助手**：同一内核同时服务终端和网页两种前端，并具备「半推」
能力（定时提醒、每日简报、周报到点自动起草）。网页前端和定时推送都必须有一个一直
运行的进程来承载，而现在的代码没有任何服务形态。本 change 为整个形态打地基：一个
本机常驻的 daemon（`ohwang serve`），把 agent 的渲染器缝隙暴露成 HTTP/WS 传输层，
让双前端共用同一 agent 内核与同一把 run_lock。

## What Changes

- 新增 `ohwang serve` 子命令：启动本机常驻守护进程，绑定 localhost 端口，提供生命
  周期管理（启动 / 健康检查 / 停止）。
- 新增 REST 传输层：`POST /run` 包装现有 `agent.run`（复用 `_run_locked` 的单飞
  队列），返回 final text；保留会话续传（SessionStore），一个网页会话 = 一个持久化会话。
- 新增 WS/SSE 流式传输层：把 agent 的五个回调（on_text / on_tool_call /
  on_tool_result / on_compact / on_turn）绑定为流式事件，让网页端能看到与终端一致的
  过程反馈。
- 并发模型：CLI、Web、cron 三路共用现有 `run_lock`，单飞执行（个人助手场景不需要
  多会话并发，明确不做多会话并行写同一工作目录）。
- 现有 TTY 反馈路径保持 CLI-only；服务端用自己的事件渲染器，不污染管道 / CI。

## Capabilities

### New Capabilities
- `server`: 本机 daemon 服务层——`ohwang serve` 常驻进程、REST/WS 传输层、单飞
  并发、会话续传。这是「个人办公助手」双前端 + 半推的地基。

### Modified Capabilities

## Impact

- 新增 `ohwang/cli.py` 的 `serve` 子命令与生命周期；新增服务模块（如
  `ohwang/services/server.py`）：HTTP/WS 适配器、会话路由、run_lock 共享。
- 依赖：本地 HTTP/WS 传输（stdlib http.server + SSE，或 aiohttp）；仅绑定
  localhost、无鉴权（个人助手单用户，多用户/鉴权明确不做）。
- 复用：`build_agent()`、`_run_locked()`、`SessionStore`、五回调渲染器缝隙——
  不改 agent 核心。
- 测试：脚本化 provider 驱动 serve 的 REST/WS 路径（复用现有 helpers），全部本机
  回环、无真实网络。
- 边界（后续 change，不在本 change 内）：Web UI 页面本身、半推通知中心与推送
  收件箱、web 端审批卡片、文件夹监听、办公领域层（PDF / 邮箱 / 日历）。
