# 协作层运行规则

> OpenCode、Codex、Claude Code 与各自 subagent 共用这一套文件化 Memory 和 Workflow。

## 开工入口

所有主 agent 开工必须依次：

1. 读 `AGENTS.md`、本文件、`协作/tasks.json`、`协作/决策协议.md`；
2. 主 agent 运行 `python3 scripts/workflow.py env-check --publish`（Windows 用 `py -3`），由此唯一模式探测外部路径；subagent 只运行不带 `--publish` 的仓库内只读自检；
3. 主 agent运行 `git pull --ff-only`并确认工作区状态；
4. 运行 `python3 scripts/workflow.py validate`（Windows 用 `py -3`）；
5. 只有主 agent 可以分配任务、创建任务分支和调度 subagent。

环境要求：**Python 3.10+**（脚本使用 PEP 604 联合类型语法）；Windows 统一经 py launcher 以 `py -3` 调用，Linux/macOS 用 `python3`。

每个 clone 初始化时还必须启用入库 Git hooks：

```text
git config core.hooksPath .githooks
git config --get core.hooksPath
```

第二条应输出 `.githooks`。hooks 是可被 `--no-verify` 绕过的本地快速反馈层，不替代 GitHub 远端保护。hooks 文件已由 `.gitattributes`（`.githooks/* -text`）固定为 LF，Windows 上 `core.autocrlf` 不会改写；clone 后仍建议将 `core.autocrlf` 设为 `false` 或 `input`。

`协作/任务台账.md`只是自动生成的人类视图。任何工具都不得手工编辑它。

## 共享 Memory

```text
协作/
├── tasks.json                 # 任务状态唯一权威
├── 任务台账.md                # 自动生成人类视图
├── 决策协议.md                # 跨工具中立决策规则
├── 决策记录/                  # decision_id 的 JSON + Markdown
├── 环境/                      # 每机独立脱敏能力快照
├── 扫描快照/                  # HOI4 本体受控元数据，不含原文
├── 扫描产出.md                # 本世界 state 归属映射
├── state-overrides/           # 按地域拆分的声明式 state 改写清单
├── 交接单/                    # 带 base/head/隔离代数的结构化交接
├── 审查记录/                  # 验证、Codex、Claude Code 报告
└── 会话记录/                  # 长程恢复摘要

任务书/                        # 任务规格（D-20260811-020）：T-XXX.json 施工图
```

本机绝对路径只存在于被忽略的 `.opencode/local.json`，不得写入上述共享文件。

## 单一主调度器

同一任务链在任一时刻只有一个主调度器。它独占以下操作：

- 修改 `协作/tasks.json`并重新生成台账；
- 分配、续租、自动回收任务；
- 创建和推送 `task/<任务ID>-g<lease_generation>`；
- 登记结构化交接；
- 调度验证、提交、推送和合并。

subagent 不得自行领取任务、修改台账、执行 Git、发布环境快照或接触游戏本体。

## 任务租约与隔离令牌

分配命令仅由主调度器运行：

```text
python3 scripts/workflow.py task assign --id T-020 --owner A/opencode
```

分配时记录：

- `base_commit`；
- 48小时租约；
- 当前 `lease_generation`；
- 唯一任务分支。

`task assign` 只允许在 `main` 上运行，且除目标机器的 `协作/环境/<machine_id>.json` 外工作区必须干净。目标快照的 `checked_at` 必须不来自未来，且距分配时刻不超过 15 分钟。命令会把已变更的目标快照、`tasks.json` 与派生台账限定在同一个租约提交中，再从该提交创建本地任务分支；不自动推送。跨机分配时，目标机器必须先运行 `env-check --publish` 并同步快照。参与调度的机器必须先通过 NTP 或操作系统时间服务同步 UTC 时钟；时钟超前会被默认拒绝。

主调度器可续租：

```text
python3 scripts/workflow.py task heartbeat --id T-020 --generation 1
```

自动回收：

```text
python3 scripts/workflow.py task reclaim-stale
```

回收会递增 `lease_generation`。旧 agent 的心跳、交接与验证结果即使稍后恢复，也会因代数不符被拒绝。

验证、测试与完成状态只由主调度器登记：

```text
python3 scripts/workflow.py task validation-result \
  --id T-020 --generation 1 --result pass \
  --report 协作/审查记录/验证-东亚.md --requires-load-test
python3 scripts/workflow.py task test-result \
  --id T-020 --generation 1 --result pass \
  --report 协作/审查记录/加载测试-东亚.md
python3 scripts/workflow.py task complete --id T-020 --generation 1
```

`handoff / validation-result / test-result / complete` 只能在 `main` 上运行，且除当前主调度机器快照和本次声明的审查报告外工作区必须干净。命令自动把快照、`tasks.json`、派生台账与交接/审查产物限定在同一提交中，提交前核对暂存区；不再手工 `git add --all`。验证/测试失败会在原 generation 内回到进行中并重开 48 小时租约；通过后进入 `ready_to_merge`。主调度器显式合并任务分支，`task complete` 只有在任务 head 已是 `main` 祖先时才会置为 `done`。

## 任务书层

`任务书/T-XXX.json`（D-20260811-020/021，schema `schemas/task-spec.schema.json` v2）是给执行 agent 的结构化施工图：目标断言、范围、设定来源矩阵、不变量、输入（快照指纹/base/依赖）、产出、limits、验收（static/dry_run/load_test）、失败语义与决策点。规则：

- 任务书 `spec_id` 必须等于文件名且任务必须存在于 `tasks.json`，由 `validate` 统一校验；
- 任务离开 `todo` 前，`inputs.snapshot_fingerprint` 与 `inputs.base_commit` 必须已解析；
- `source_matrix` 出现 `pending` 条目时任务必须处于 `decision_required`，不得被领取；
- 阶段 1（州界重划）将增补 `province_scope`、`dry_run_stats` 字段，schema 版本演进。

## 任务执行原则（D-20260811-021）

1. **任务拆小**：按地域/主题拆分，每任务独立分支与交接；
2. **scope 强制**：`task handoff` 校验 base..head 变更文件必须全部 ∈ 任务书 `outputs`，越界即拒绝；
3. **先验收后继续**：状态机门禁，验证/测试通过前不得合并；
4. **自动测试优先**：统一校验器 + 单元测试 + hooks + CI + 干跑/加载测试；
5. **失败限制**：`failure_count`/`stage_failure_count` 计数，超过任务书 `limits`（max_retries/max_files/max_same_error）置 `blocked`（FAIL：停止并保存现场）；
6. **checkpoint 回滚**：assign 时 checkpoint=base_commit，通过后自动推进；失败且 `revert_on_fail` 时自动回滚（分支 reset 至 checkpoint + 代数+1），`task checkpoint` 可显式登记；
7. **禁止目标漂移**：仅解决当前任务验收条件内问题，越界改动被 scope 强制拒绝；
8. **状态持久化**：tasks.json/决策/交接/审查/快照全部落盘，不信对话记忆。

终态语义：PASS=`ready_to_merge`（通过验证与测试）、BLOCKED=`decision_required`（等待设计决策）、FAIL=`blocked`（超限或不可恢复，停止并保存现场）。

## 受控本体快照

只有具备 `snapshot_export=true` 的机器可由主 agent 显式运行：

```text
python3 scripts/workflow.py snapshot-export
```

导出器只读 `<game_path>/history/states/*.txt`，只向工作区写 state ID、相对文件名、province 编号列表（schema v2，D-20260811-018）、SHA-256、游戏版本和总体指纹。禁止复制原版脚本正文。快照校验强制"每个 province 恰好属于一个 state"的全局唯一归属不变量，由统一校验器在 CI、本地与干跑三处一致执行。检测到本体指纹改变时，快照状态变为 `stale`，依赖任务和加载测试全部阻断，直到主调度器审查并提交刷新结果。

## 受控 state 转换

`D-20260811-004` 规定 state 正文不进入受控快照，也不向 subagent 暴露。按地域执行任务只提交 `协作/state-overrides/*.json`：每份清单必须通过 `schemas/state-overrides.schema.json`，并绑定整体快照指纹、来源相对路径与单文件 SHA-256。

机器 C 可以开发转换器和验证清单，但不能运行真实转换。只有主 agent 在同时满足 `snapshot_export=true`、`mod_execution=true` 且快照状态为 `current` 的机器上才能执行：

```text
python3 scripts/workflow.py state-build \
  --override 协作/state-overrides/东亚.json \
  --override 协作/state-overrides/欧洲.json
```

命令固定从本机 `.opencode/local.json: game_path` 只读输入，拒绝外部改写清单路径；它先校验全部输入和 SHA，再为快照中的**全部** states 生成完整 `mod/history/states/` 覆盖文件。未被清单声明的内容保持原样。唯一字段重复、state ID/路径/SHA 不符、多个清单修改同一 state 或快照过期时一律拒绝，不做猜测性修复。

实际生成由 T-028 执行。T-009、T-020—T-027 只产出声明式清单，不得直接复制或编辑本体 state 正文。

## 环境能力与跨机同步

能力由脚本实测派生，不接受手填声明：

- `dialog_development`：逐轮对话式开发；
- `snapshot_export`：可只读导出本体元数据；
- `mod_execution`：存在可用且未过期的共享快照；
- `static_validation`：可运行统一静态校验；
- `load_test`：游戏、本地用户目录和启动程序满足加载测试条件。

总体档位 `light/partial/full`只供人查看，任务调度以分项能力为准。每机发布 `协作/环境/<machine_id>.json`，其中禁止出现本地路径。

## 交接与验证

执行 agent 把改动证据报告给主调度器。主调度器在确认任务代数仍有效后登记：

跨机交接先由主调度器显式同步远程跟踪分支（命令不会隐式访问网络）：

```text
git fetch origin
```

```text
python3 scripts/workflow.py task handoff \
  --id T-020 --generation 1 --head <40位SHA> \
  --changed-file 协作/state-overrides/东亚.json
```

验证对象必须是交接单的完整 `base_commit..head_commit`，不能依赖可能为空的工作区 diff。

登记交接时，`head_commit` 必须等于本地 `task/...` 或已 fetch 的 `origin/task/...` 实际 tip；仅是 base 的任意后代不再被接受。本地与远程跟踪分支同时存在但 tip 不一致时默认拒绝，不猜测哪个有效。

## OpenCode 权限冒烟验证

每次升级 OpenCode 或修改 agent 权限后，在机器 A/B/C 各做一次真实工具调用冒烟验证：

1. `execute` 和 `verify` 运行 `python3 scripts/workflow.py env-check` 应允许；
2. 两者运行 `git status --short` 应被拒绝；
3. `verify` 运行带 40 位 SHA 的 `validate --base ... --head ...` 应允许；
4. `verify` 写入非 `协作/审查记录/验证-*.md` 路径应被拒绝。

先用 `opencode debug agent execute` 和 `opencode debug agent verify` 核对解析结果，再做上述运行时检查；只看 debug 输出不算完成冒烟验证。

验证至少包含：

1. 设定来源可追溯；
2. 仓库写入路径符合当前 agent 权限；
3. 设定层改动同时更新00卷修订记录并关联 `decision_id`；
4. 待定项没有在提交区间内被静默删除或填实；`待定/待确认/【拟定】/【待推演】` 的净消失必须由同 commit 决策 JSON 的 `resolved_pending` 逐项授权；
5. `lease_generation`、任务分支、base/head 全部匹配。

`resolved_pending` 以原标记行规范化文本的 SHA-256 绑定证据；校验失败会输出 `path`、`line_sha256`、缺少的 `occurrences` 和原行摘要。决策记录按该输出填写解决摘要，不得用只匹配目录的泛化决策冒充用户授权。

游戏本体安全不再由仓库 diff 猜测，而由“agent无外部访问权 + 仅主 agent 可运行固定只读导出器”保证。

## 决策与双轨语言

重大抉择和模糊需求完整遵循 `协作/决策协议.md`。正式技术说明之后必须附通俗解释；一次只问一个问题；拍板后生成结构化决策记录。

依据 `D-20260811-005`，模糊需求访谈已恢复完整收束门槛：首次假设与置信度、每问当前猜测、应然性回答追问、六字段重述（含 Why now 与 Out of scope）、三问预测停止检查和明确确认。`whatever you think`、`sounds good` 等弱确认不能触发开工。具体措辞与例外只以 `协作/决策协议.md` 为准，工具专用 skill 不得复制第二套正文。

统一校验器会检查上述关键规则锚点和 `teg-interview-me` 的短适配器形态；删减协议或把流程复制回适配器都会使验证失败。

## 会话摘要

```text
## 会话：[agent] - [任务] - [日期]
- task_id / lease_generation：...
- base_commit / 当前 head：...
- 已完成：...
- decision_ids：...
- 遗留/阻塞：...
- 下一入口：...
```

## 统一验证

本地与 CI 使用同一命令：

```text
python3 scripts/workflow.py validate
```

提交前检查 Git index 中即将形成的同 commit 边界：

```text
python3 scripts/workflow.py validate --staged
```

`.githooks/pre-commit` 自动运行上述 staged 校验和标准库单元测试；`.githooks/pre-push` 从 Git hook stdin 读取本地/远端 SHA，分别传给 `--base` 与 `--head`，并拒绝无法确定基线的新分支推送。Windows 由 `py -3` 运行，Linux/macOS 优先使用 `python3`。

`schemas/` 是共享 JSON Schema 权威约束；Python 标准库校验器直接执行项目使用的 schema 子集，并额外检查权限白名单、自动生成文件、tag 数量、隔离令牌和提交区间规则。设定层和协作核心规则按每个 commit 检查，不得用后续 commit 补齐同 commit 义务。

## GitHub main 远端保护

仓库管理员必须在 GitHub main ruleset／分支保护中确认：

1. Enforcement 为 Active，目标分支为 `main`；
2. 必须通过 Pull Request，禁止未经审查的直接更新；
3. 必需状态检查包含 `workflow-integrity / validate`；
4. 禁止 force push，并限制或清空 bypass 列表；
5. 规则修改后用普通维护者身份做一次失败 PR 冒烟，确认不能合并。

`push main` 上的 Actions 发生在远端接受提交之后，只能事后报警。只有上述远端规则实际启用时，PR 检查才可称为不可绕过的合并闸门；未核实远端设置时不得作此声明。
