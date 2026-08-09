## 1. serve 命令与 HTTP 骨架

- [x] 1.1 `ohwang/cli.py` 新增 `serve` 子命令（`--host`/`--port`），复用
      `build_agent(args, run_lock)` 组装后调用 `ohwang/services/server.py` 的
      `run_server(...)`；server 模块只接收它需要的装配件（agent、run_lock、
      session_store、memory_extractor），便于测试直接构造。
- [x] 1.2 新建 `ohwang/services/server.py`：`ThreadingHTTPServer` + 路由
      （`/health`、`/run`、`/stream`）；`/health` 不拿锁直接返回 ready。
- [x] 1.3 单元测试：serve 启动后 `/health` 返回 200 ready；绑定仅限 127.0.0.1
      （用 0 端口起服验证监听地址）。

## 2. REST /run（同步单飞）

- [x] 2.1 `POST /run` 实现：body `{message, session_id?}`；`with run_lock:
      agent.run(...)`，run 后镜像 `_run_once` 后置（`memory_extractor.maybe_extract`
      + `session_store.save`），返回 `{session_id, final_text}`。
- [x] 2.2 单飞测试：脚本化 provider 造慢响应，第二个请求排队直到第一个完成。
- [x] 2.3 会话测试：无 `session_id` 创建新会话并返回 id；带 `session_id` 续传历史
      （对齐 `test_scenario_save_resume`）。

## 3. SSE /stream（流式传输层）

- [x] 3.1 `POST /stream` 实现：把五回调（on_text / on_tool_call / on_tool_result /
      on_compact / on_turn）写成 SSE 事件（event: text / tool_call / tool_result /
      compact / turn），结束发 `done`（携带 session_id），异常发 `error`。
- [x] 3.2 测试：脚本化 provider 逐条断言 text 与 tool_call 事件先于 `done`；
      工具报错时 `tool_result` 事件带 is_error。
- [x] 3.3 测试：流式模式下 on_turn 每轮进度事件出现。

## 4. 生命周期与文档

- [x] 4.1 SIGINT/SIGTERM 优雅关闭：停止接收新连接、在跑 run 完成、端口释放；测试
      可反复启动/停止且不泄漏端口。
- [x] 4.2 `docs/CHANGELOG.md` 记录 server 能力 + 测试演进数字。
- [x] 4.3 `docs/ARCHITECTURE.md`：模块树加 server 相关行；§3.5 表补 server 行。

## 5. 绿套件

- [x] 5.1 跑 `.venv\Scripts\python.exe -m pytest -q` 全绿（585 passed）。
