# OhWangAgent 项目约定

## 开发流程

每次完成一项优化或功能修改，必须三件事齐全才算完成：

1. **补齐单元测试**：为改动新增/更新的行为写测试，运行 `pytest -q` 确认全绿。
2. **更新文档**：同步更新 `docs/CHANGELOG.md`（记录变更）与 `docs/ARCHITECTURE.md`（结构/接线变化）。
3. **提交代码**：`git commit` 提交改动（提交信息遵循现有风格：`feat`/`fix`/`docs` + 简短说明 + 测试规模）。

## 环境

- 虚拟环境：`.venv`；回归命令：`$env:PYTHONPATH="D:\ai-project\OhWangAgent"; .venv\Scripts\python.exe -m pytest -q`
- 远程：`https://github.com/wangbc13hust/OhWangAgent.git`，推送完成后确认远端更新。

## 约定要点

- 不使用 ruff/pyright 作为门禁，测试通过即可提交。
- 文档更新范围：CHANGELOG 必更，ARCHITECTURE 仅在结构/接线变化时更。
