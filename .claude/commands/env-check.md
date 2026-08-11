# 环境与能力自检

运行：

```text
python3 scripts/workflow.py env-check --publish
```

Windows 使用 `py -3 scripts/workflow.py env-check --publish`。

不得根据路径存在与否自行声称 full。后续任务必须逐项满足 `协作/tasks.json` 的 `required_capabilities`；快照为 stale 时停止所有依赖任务。

`--publish` 只由主 agent 使用并是唯一会探测外部路径的模式；subagent 运行不带 `--publish` 的仓库内自检。
