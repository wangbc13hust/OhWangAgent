# OhWangAgent 项目约定

OhWangAgent 是一个镜像 Claude Code 的 Python 办公 agent 框架（CLI）。以下约定对该仓库内工作的 AI 工具与人通用。

## 开发流程（每次改动三件事齐全才算完成）

1. **补齐单元测试**：为新增/更新的行为写测试，先跑单文件 `.venv\Scripts\python.exe -m pytest tests/test_xxx.py -q`，合并前跑全量 `.venv\Scripts\python.exe -m pytest -q` 确认全绿——**不通过不提交**。
2. **同步文档**：`docs/CHANGELOG.md` 必更（变更 + 测试演进数字）；`docs/ARCHITECTURE.md` 仅当结构/接线/服务/flag 变化时更。
3. **提交并推送**：中文 message，`feat`/`fix`/`docs` 前缀（可带范围如 `(review)`）+ 简短说明（附测试规模），结尾 `Co-Authored-By: Claude <noreply@anthropic.com>`；直接提交 main，`git push origin main` 后确认远端更新。

## 环境

- 虚拟环境：`.venv`（Windows 11 / Git Bash）
- 全量回归：`$env:PYTHONPATH="D:\ai-project\OhWangAgent"; .venv\Scripts\python.exe -m pytest -q`
- 远程：`https://github.com/wangbc13hust/OhWangAgent.git`

## 约定要点

- 不以 ruff/pyright 作为门禁，测试通过即可提交。
- 文档范围：CHANGELOG 必更，ARCHITECTURE 仅在结构/接线变化时更。
- **文件写入分块**：写入文件时控制每次写入文本内容的大小；内容较大时先用 Write 写主体、再用 Edit 续写（可分多次写入），避免大段内容一次性写入出现 file error；写完后 Read 回读确认完整性。
