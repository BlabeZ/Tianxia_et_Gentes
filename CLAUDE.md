# Project Instructions（Claude Code 入口）

> 本文件是 Claude Code 的项目指令入口。Claude Code 在本仓库内工作时**必须先读取**以下文件，再开始任何 debug/review/方案设计：

1. `AGENTS.md`——项目硬约束（重大抉择必须提问、禁止猜测、本体只读）
2. `协作/README.md`——协作层运行规则
3. `协作/tasks.json`——机器可读任务权威来源
4. `协作/决策协议.md`——重大决策与模糊需求的中立流程
5. `docs/协作框架.md`——完整架构说明

## Claude Code 在本项目的职责

- **少量使用**：debug、bug 修复、review、方案设计
- 触发：用户在总装/验证期手动启动
- 产出归档：所有 review/debug 结果写入 `协作/审查记录/cc-*.md`（命名如 `cc-bug修复-总装.md`）
- 不得修改游戏本体（硬约束3，路径见 `.opencode/local.json: game_path`）
- 不得擅自补全设定（硬约束2，待定/待确认标注保留）
- 开工前跑 `/env-check`（实际调用统一 Python 门禁）并按任务的 `required_capabilities` 判断许可
- Claude Code 主进程可充当主调度器；subagent 不得修改任务状态、执行 Git 或直接访问游戏本体

## 交接协议

会话结束写会话摘要到 `协作/会话记录/cc-<日期>-<任务>.md`，格式见 `协作/README.md`；交接由主调度器登记结构化 base/head/代数。
