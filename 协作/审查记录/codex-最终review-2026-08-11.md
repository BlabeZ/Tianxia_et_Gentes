# Codex 最终 Review：协作框架与 grill-me 要求

> 日期：2026-08-11｜审查区间：`origin/main..df01891be33f4aefa4b71d539d371785b46a4e8f`｜决策依据：`D-20260810-001`

## 最终判定

**有条件不通过：当前改动已满足协作框架的大部分静态基础要求，但不能确认为已完整满足最初要求和 grill-me/interview-me 意见。**

已成立的部分包括：单一主调度器规则、脱敏环境快照、受控本体元数据快照、Python 3 标准库门禁、`tasks.json` 权威台账、48 小时租约与 `lease_generation`、base/head 交接、GitHub Actions 入口、命名空间化的 OpenCode skill 适配器、双轨中文与结构化决策记录。

## 阻塞项

### 1. state 执行链路没有闭环

- `snapshot-export` 只导出 state ID、localisation key、相对文件名、province 数量和哈希，不导出 province ID 列表、state category 或 history 块（`scripts/workflow.py:156-173, 465-493`）。
- execute agent 却被要求改写 `mod/history/states/*.txt` 中的 `owner/add_core_of/manpower`（`.opencode/agent/execute.md:30-36`）。
- 当前仓库尚无 `mod/`，也没有一个受控主进程可以在 full 机上读取原 state、应用映射并直接生成 mod 覆盖文件。

因此 `mod_execution=true` 目前只表示“存在快照”（`scripts/workflow.py:390-404`），不等于具备完成阶段 B 的输入。这不影响“agent 不直接读本体”的安全目标，但使预定的 mod 生成流程无法执行。

### 2. 独立任务分支只被记录，没有创建或验证

- `task assign` 仅把分支名字写入 JSON，没有创建分支（`scripts/workflow.py:601-633`）。
- `task handoff` 只验证 head 是 base 的后代，不验证 head 是记录分支的 tip（`scripts/workflow.py:686-730`）。
- 这与 `D-20260810-001` 的“每一租约代使用独立任务分支”及 `协作/README.md:37-43`“主调度器创建和推送分支”之间存在实现缺口。

### 3. 任务状态机无法通过统一入口完成后半段

- CLI 只有 `assign/heartbeat/reclaim-stale/handoff`（`scripts/workflow.py:1083-1104`）。
- `handoff` 只能将任务置为 `pending_validation`；没有将验证结果登记为 `pending_test/done`、验证失败回退、加载测试通过或阻塞的受控命令。

这意味着文档声明的“待办 → 进行中 → 待验证 → 待测试/完成”无法仅依靠统一工作流命令闭环。

## 重要缺口

### 4. CI 尚不能证明“同 commit 修订记录”与真实 decision 关联

`validate_change_range` 只检查整个 base..head 区间内是否同时出现设定文件、00 卷和任意决策记录路径（`scripts/workflow.py:1004-1034`）。它不会：

- 逐 commit 检查设定变更与00卷修订行是否同一 commit；
- 验证00卷确有新增对应事项/决定/影响文件的表格行；
- 验证决策内容与本次变更相关，而不是任意 `D-*.json`。

对抗性测试确认：只要变更文件集同时包含 `Settings/example.md`、`00-总览与索引.md` 和任意决策 JSON，即使无法证明同 commit/真关联，当前函数仍返回通过。

### 5. JSON Schema 是文档资产，未被统一门禁完整执行

`validate_decisions` 只检查少数字段（`scripts/workflow.py:864-881`）。对抗性测试证明：缺少 schema 要求的 `title/confirmed_by/scope/affected_files` 时仍可通过。tasks/environment/handoff 也是手写子集验证，不是完整 schema 校验。

### 6. 环境快照的绝对路径检查可绕过

`validate_environment` 只匹配 Windows 反斜杠盘符、`/home/` 和 `/Users/`（`scripts/workflow.py:805-840`）。对抗性测试确认 `/tmp/secret`、`/mnt/c/secret`、`C:/secret` 和 UNC 路径均不会被发现。当前生成器本身没有输出这些路径，但 CI 不足以执行文档中“禁止任何绝对路径”的通用保证。

### 7. grill-me 主干已保留，interview-me 细节仅部分保留

与改动前 `origin/main:.opencode/skills/grill-me/SKILL.md` 相比，中立协议已保留：question tool 优先、一次一问、2—4 个具体选项、工具可查事实不反问、决策树完成后总结；项目协议还增加了双轨中文、逐项优缺点和明确推荐。

但与改动前 `origin/main:.opencode/skills/interview-me/SKILL.md` 相比，`协作/决策协议.md:29-31` 未完整保留：

- 每个后续问题都带当前 guess；
- `Why now` 作为最终重述字段；
- “能预测用户对下三个问题的反应”的95% 停止检查；
- 对“可扩展/现代/最佳实践”类应然性回答的特定追问；
- 明确拒绝把“sounds good / whatever you think”当作终态确认。

如果用户所说的“grillme 意见”包括原 interview-me 的全部收束规则，当前不能判定为完整符合。

## 次要风险

1. `load_test=true` 只验证游戏路径、候选可执行文件和用户目录存在（`scripts/workflow.py:384-405`），不验证启动器可执行、mod 安装/选中或真实加载。它更准确的含义是“具备加载测试前置条件”。
2. 任务分配只读环境快照中的布尔能力（`scripts/workflow.py:590-598`），不检查 `checked_at`新鲜度；目前仅靠文档要求“分配前在目标机重跑”。
3. 主 agent 每次必跑 `env-check --publish` 都会改写已跟踪的 `checked_at`，使原本干净的工作区在“确认工作区状态”之前必然变脏。本次 review 已实际复现。

## 验证证据

- `python3 -m unittest discover -s tests -v`：15/15 通过。
- `python3 scripts/workflow.py validate --base origin/main --head HEAD`：通过。
- 对抗性检查：决策 schema 必填字段可绕过；多种绝对路径可绕过；区间级设定联动检查不能证明同 commit。
- C 机环境：`light`；`dialog_development/static_validation=true`，`snapshot_export/mod_execution/load_test=false`。
- 本次未读取或修改 HOI4 本体。官方网络资料检索因网络错误未完成；state 执行链路判定仅基于本仓库的快照字段与 execute 任务的输入/输出矛盾。

## 验收前必须完成

1. 设计并实现一条不向 subagent 暴露原文、但能在 full 机生成完整 mod state 文件的受控转换链路。
2. 让任务分配真正创建/校验租约分支，并补齐验证、测试、完成与回退状态迁移。
3. 将“同 commit 修订记录”、决策真关联、完整 schema 约束和通用路径脱敏变成可验证的硬门禁。
4. 明确拍板：interview-me 的被省略规则是有意简化，还是应该补回中立协议。
5. 在 full 机刷新受控快照并完成端到端冒烟/加载测试；当前 C 机不具备该能力。
