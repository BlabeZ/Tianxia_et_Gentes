# 协作层运行规则

> OpenCode、Codex、Claude Code 与各自 subagent 共用这一套文件化 Memory 和 Workflow。

## 开工入口

所有主 agent 开工必须依次：

1. 读 `AGENTS.md`、本文件、`协作/tasks.json`、`协作/决策协议.md`；
2. 主 agent 运行 `python3 scripts/workflow.py env-check --publish`（Windows 用 `py -3`），由此唯一模式探测外部路径；subagent 只运行不带 `--publish` 的仓库内只读自检；
3. 主 agent运行 `git pull --ff-only`并确认工作区状态；
4. 运行 `python3 scripts/workflow.py validate`（Windows 用 `py -3`）；
5. 只有主 agent 可以分配任务、创建任务分支和调度 subagent。

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
├── 交接单/                    # 带 base/head/隔离代数的结构化交接
├── 审查记录/                  # 验证、Codex、Claude Code 报告
└── 会话记录/                  # 长程恢复摘要
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

`task assign` 只允许在干净的 `main` 上运行。命令会自动提交 `tasks.json` 与派生台账的租约变更，然后创建对应本地任务分支；不自动推送。主调度器审查租约提交后，显式推送 `main` 和任务分支。

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

状态命令只能在干净 `main` 上运行，审查报告必须已位于 `协作/审查记录/`。验证/测试失败会在原 generation 内回到进行中并重开 48 小时租约；通过后进入 `ready_to_merge`。主调度器显式合并任务分支，`task complete` 只有在任务 head 已是 `main` 祖先时才会置为 `done`。每次状态命令后由主调度器显式提交台账。

## 受控本体快照

只有具备 `snapshot_export=true` 的机器可由主 agent 显式运行：

```text
python3 scripts/workflow.py snapshot-export
```

导出器只读 `<game_path>/history/states/*.txt`，只向工作区写 state ID、相对文件名、province 数量、SHA-256、游戏版本和总体指纹。禁止复制原版脚本正文。

scan/execute/verify subagent 都不获得游戏路径或外部目录访问权。它们只消费已提交的快照。检测到本体指纹改变时，快照状态变为 `stale`，依赖任务和加载测试全部阻断，直到主调度器审查并提交刷新结果。

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

```text
python3 scripts/workflow.py task handoff \
  --id T-020 --generation 1 --head <40位SHA> \
  --changed-file mod/history/states/example.txt
```

验证对象必须是交接单的完整 `base_commit..head_commit`，不能依赖可能为空的工作区 diff。

登记交接时，`head_commit` 还必须等于台账所记本地任务分支的实际 tip；仅是 base 的任意后代不再被接受。

验证至少包含：

1. 设定来源可追溯；
2. 仓库写入路径符合当前 agent 权限；
3. 设定层改动同时更新00卷修订记录并关联 `decision_id`；
4. 待定项没有在提交区间内被静默删除或填实；
5. `lease_generation`、任务分支、base/head 全部匹配。

游戏本体安全不再由仓库 diff 猜测，而由“agent无外部访问权 + 仅主 agent 可运行固定只读导出器”保证。

## 决策与双轨语言

重大抉择和模糊需求完整遵循 `协作/决策协议.md`。正式技术说明之后必须附通俗解释；一次只问一个问题；拍板后生成结构化决策记录。

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

`schemas/` 是共享 JSON Schema 权威约束；Python 标准库校验器直接执行项目使用的 schema 子集，并额外检查权限白名单、自动生成文件、tag 数量、隔离令牌和提交区间规则。设定层和协作核心规则按每个 commit 检查，不得用后续 commit 补齐同 commit 义务。
