# Project Instructions（Claude Code 入口）

> 本文件是 Claude Code 的项目指令入口。Claude Code 在本仓库内工作时**必须先读取**以下文件，再开始任何 debug/review/方案设计：

1. `AGENTS.md`——项目硬约束（重大抉择必须提问、禁止猜测、本体只读）
2. `docs/协作框架.md`——多 agent 协作框架（工具分工/Memory/Workflow/验证清单/多机异构）
3. `协作/README.md`——协作层说明与开工必读
4. `协作/任务台账.md`——任务状态机（领任务前必读，按状态领取）
5. `.opencode/local.json`——本机能力档（缺失/无效一律判 light，默认拒绝长程/测试）

## Claude Code 在本项目的职责

- **少量使用**：debug、bug 修复、review、方案设计
- 触发：用户在总装/验证期手动启动
- 产出归档：所有 review/debug 结果写入 `协作/审查记录/cc-*.md`（命名如 `cc-bug修复-总装.md`）
- 不得修改游戏本体（硬约束3，路径见 `.opencode/local.json: game_path`）
- 不得擅自补全设定（硬约束2，待定/待确认标注保留）
- 开工前跑 `/env-check` 确认本机能力档

## 交接协议

会话结束写会话摘要到 `协作/会话记录/cc-<日期>-<任务>.md`，格式见 `协作/README.md`。
