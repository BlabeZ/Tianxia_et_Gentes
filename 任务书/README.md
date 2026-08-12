# 任务书

> 任务书是给执行 agent 的结构化施工图（D-20260811-020/021，schema v3，必填 `requirement_ref`）。

## 目录结构（D-20260812-021）

```
任务书/
├── R-001-地图改造/   T-028（活动层）+ _归档/（已完成的旧任务书）
├── R-002-工业槽位/   T-033, T-034（活动层）+ _归档/
├── R-003-国家快照/   T-036（活动层）+ _归档/
├── R-005-协作层基础设施/  _归档/
└── README.md
```

- 任务书按需求（`需求/R-XXX.json`）分文件夹存放；`_归档/` 收容 completed 任务书；
- `task complete` 自动将任务书 `git mv` 至所属需求子目录 `_归档/`；
- 校验器只对活动层做完整校验（requirement_ref/inputs/scope/limits/load_test）；归档层仅 JSON 与 schema 格式校验；done 任务书滞留活动层会被报告。

## 规则

1. 文件名 `T-XXX.json`，`spec_id` 必须等于文件名，`requirement_ref` 必须指向存在的 `需求/R-XXX.json`，且任务必须存在于 `协作/tasks.json`；
2. 每份任务书必须通过 `schemas/task-spec.schema.json`，由 `python3 scripts/workflow.py validate` 统一校验；
3. 任务离开 `todo` 前，`inputs.snapshot_fingerprint` 与 `inputs.base_commit` 必须已解析为真实值；
4. `source_matrix` 出现 `pending` 条目时，对应任务必须处于 `decision_required`，不得被领取；
5. `outputs` 是交接的改动文件白名单：`task handoff` 时 base..head 变更必须全部 ∈ outputs（scope 强制）；
6. `limits.max_retries`/`max_files`/`max_same_error` 是失败上限：超限自动置 `blocked`（FAIL）；
7. `revert_on_fail` 启用时，验证/测试失败自动回滚任务分支至 `checkpoint_commit` 并递增代数；
8. 任务书与相关决策记录同 commit 入库；阶段 1 将随州界重划（T-041）增补 `province_scope`、`dry_run_stats` 等字段（schema 版本演进，不破坏 v3）。

## 目录迁移记录（D-20260812-021）

2026-08-12：任务书由平铺 `任务书/T-XXX.json` 迁移为按需求子文件夹分批（`任务书/R-XXX-名称/`），schema v2→v3 补必填 `requirement_ref`；17 份 done 任务书直接入 `_归档/`，4 份非 done（T-028/T-033/T-034/T-036）留活动层；T-041（州界重划）新建于 R-001-地图改造/。历史决策记录中的 `任务书/T-XXX.json` 路径为迁移前事实，不做修改。

## T-028 机器 A 执行指南（受控生成）

仅主 agent 在 `snapshot_export=true` + `mod_execution=true` + 快照 `current` 的机器执行；正式生成前必须先干跑确认：

```text
# 1. 同步与自检
git pull --ff-only
py -3 scripts/workflow.py env-check --publish
py -3 scripts/workflow.py validate

# 2. 干跑：只输出差异统计（新增/修改/不变/遗留），不落盘
#    当前共 8 份 JSON：7 份地域声明 + 1 份经济与工业声明；大洋洲为空声明，无 JSON。
py -3 scripts/workflow.py state-build --dry-run ^
  --override 协作/state-overrides/东亚.json ^
  --override 协作/state-overrides/东南亚与南亚.json ^
  --override 协作/state-overrides/中亚与西亚.json ^
  --override 协作/state-overrides/欧洲.json ^
  --override 协作/state-overrides/非洲.json ^
  --override 协作/state-overrides/北美.json ^
  --override 协作/state-overrides/拉丁美洲.json ^
  --override 协作/state-overrides/经济与工业.json

# 3. 核对干跑输出：首次生成应几乎全为新增、无遗留异常后正式生成
#    同上命令去掉 --dry-run（Linux 用 \ 续行）

# 4. 校验并提交（生成物由主调度器审查后推送）
py -3 scripts/workflow.py validate

# 5. 加载测试：启动游戏加载 mod，确认无 state 解析错误
#    T-028 任务书 requires_load_test=true，验证通过后状态机强制进入 pending_test。
#    失败即回滚：删除 mod/history/states 后从步骤 2 重来
```
