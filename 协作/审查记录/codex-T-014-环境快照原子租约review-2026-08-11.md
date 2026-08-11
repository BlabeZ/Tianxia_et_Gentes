# T-014 环境快照原子租约审查

> 审查者：Codex｜日期：2026-08-11｜结论：**PASS**

## 审查范围

- 任务：`T-014`
- 决策：`D-20260811-006`
- 完整提交区间：`2a448c0c8d37814ef0ce6bbccb360f2a393b62a8..0362bdfc9a7c61e20dda92da359f2e44266c9ca0`

## 结果

1. `task assign` 仍只能在 `main` 上运行；工作区仅允许当次 owner 对应的脱敏环境快照作为额外变更，其他已跟踪、未跟踪或暂存变更会被拒绝。
2. 负责人快照先经 JSON Schema 和 `machine_id` 核对，再要求 `checked_at` 不晚于分配时刻且时龄不超过 15 分钟；所需多项能力布尔值仍逐项判定。
3. 写入租约后，暂存区文件集必须包含 `tasks.json` 与派生台账，且最多再包含目标快照。租约提交成功后才从该提交创建任务分支，流程未引入自动 push。
4. 临时 Git 仓库集成测试已验证：新快照、租约 JSON 和 Markdown 台账位于同一提交，任务分支 tip 指向该提交，完成后工作区干净。

## 验证证据

- `python3 -m unittest discover -s tests -v`：44/44 通过。
- `python3 scripts/workflow.py validate`：通过。
- `python3 scripts/workflow.py validate --base 2a448c0c8d37814ef0ce6bbccb360f2a393b62a8 --head 0362bdfc9a7c61e20dda92da359f2e44266c9ca0`：通过。
- `git diff --check`：通过。

## 边界

本审查证明了本地 Git 原子性与快照时间门禁，不把真实跨机 Git 传输视为已执行。跨机调度仍必须由目标机器实测发布快照后同步；机器时钟若超前，系统会默认拒绝，不会宽松接受。
