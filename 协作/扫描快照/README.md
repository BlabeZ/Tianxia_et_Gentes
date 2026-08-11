# HOI4 本体受控快照

本目录只保存由 full/partial 机显式导出的结构化元数据：

- `states.json`：供 agent 和校验器消费；
- `states-summary.md`：供人类审查；
- 不复制 `history/states/*.txt` 原文。

导出命令：

```text
python3 scripts/workflow.py snapshot-export
```

Windows 使用 `py -3 scripts/workflow.py snapshot-export`。

如果环境检查发现本体指纹与已提交快照不一致，相关执行和加载测试必须停止，直到主调度器审查并提交新快照。
