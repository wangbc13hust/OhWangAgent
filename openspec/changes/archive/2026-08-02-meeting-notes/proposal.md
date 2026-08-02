## Why

会议纪要是项目的核心定位（CLAUDE.md 的示例场景），但目前只是模型的即兴
输出：结构不固定、落盘位置随机、待办不进入任务系统。这个 change 把"会议
纪要"固化为一个有行为契约的能力——固定结构、固定落盘路径、待办同步——
让每次产出可预期、可验证、可归档。

## What Changes

- 新增 `meeting-notes` 能力：把会议记录/转录/随手笔记转成结构化纪要。
- 固定纪要结构：会议信息（日期/主题/参与人）+ 议题与结论/决策 + 待办事项。
- 固定输出位置：`docs/meetings/<日期>-<主题>.md`，目录不存在时自动创建。
- 待办事项同步进任务列表（复用既有 todo 工具），带状态与优先级。
- 只能从会议材料中得出结论与待办；材料缺失的信息标注「待确认」，不臆造。

## Capabilities

### New Capabilities
- `meeting-notes`: 结构化会议纪要生成——从原始会议材料产出固定结构的
  markdown 纪要，落盘到固定路径，并把待办同步进任务列表。

### Modified Capabilities
（无——这是全新能力，不修改既有规格。）

## Impact

- `ohwang/prompts.py`：加入纪要结构指引块（结构契约、命名规则、待确认规则）。
- `ohwang/services/meeting_notes.py`（新增）：文件名推导/清理小工具。
- `tests/test_scenarios.py`：既有 `test_scenario_meeting_notes` 断言旧行为
  （根目录文件名、无结构/待办），将更新为新契约；并补待确认与无待办场景。
- 无新依赖、不引第三方服务、不改权限模型与 hooks。
