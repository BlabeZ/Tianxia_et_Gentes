---
description: 任务开工前强制环境与能力自检（能力闸门）。所有 agent/subagent 启动第一步必跑。
agent: build
---

# 环境与能力自检（/env-check）

运行下列统一入口，不得用模型自行猜测能力：

```text
python3 scripts/workflow.py env-check --publish
```

Windows 使用 `py -3 scripts/workflow.py env-check --publish`。

## 步骤

脚本负责：

1. 校验 `.opencode/local.json` 字段与类型；缺失或无效时默认拒绝本体相关能力。只有主 agent 的 `--publish` 模式会探测外部路径。
2. 分别派生 `dialog_development/snapshot_export/mod_execution/static_validation/load_test`。
3. 比对已提交快照与本体指纹；不一致时将快照标为 `stale` 并封锁依赖能力。
4. 生成不含本地路径的 `协作/环境/<machine_id>.json`。
5. 报告 Git 工作树状态；同步远端由主调度器在开工前单独执行。

```
== 环境自检 ==
profile: <light|partial|full>
capability.<name>: <true|false>
snapshot_status: <missing|available|current|stale>
```

## 默认拒绝（安全铁律）

- 任务按 `required_capabilities` 逐项匹配，不再只看 full/light 标签
- `snapshot_status=stale` 时禁止 scan/execute/load_test，直至主调度器显式刷新快照
- subagent 只能运行不带 `--publish` 的仓库内只读自检，不探测游戏、Workshop 或用户目录；发布环境快照由主 agent 执行

## 失败处理

- 任一必需能力为 false → 不得分配对应任务
- 环境快照疑似包含绝对路径 → 统一校验器和 CI 直接失败
- 本体快照只允许主 agent 在 full/partial 机运行 `snapshot-export`
