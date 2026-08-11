# 任务书

> 任务书是给执行 agent 的结构化施工图（D-20260811-020，schema v1）。

## 规则

1. 文件名 `T-XXX.json`，`spec_id` 必须等于文件名，且任务必须存在于 `协作/tasks.json`；
2. 每份任务书必须通过 `schemas/task-spec.schema.json`，由 `python3 scripts/workflow.py validate` 统一校验；
3. 任务离开 `todo` 前，`inputs.snapshot_fingerprint` 与 `inputs.base_commit` 必须已解析为真实值；
4. `source_matrix` 出现 `pending` 条目时，对应任务必须处于 `decision_required`，不得被领取；
5. 任务书与相关决策记录同 commit 入库；阶段 1 将随州界重划增补 `province_scope`、`dry_run_stats` 等字段（schema 版本演进，不破坏 v1）。
