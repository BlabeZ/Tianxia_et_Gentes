# HOI4 本体受控快照

本目录只保存由 full/partial 机显式导出的结构化元数据：

- `states.json`：供 agent 和校验器消费（当前导出 schema v3，含 province、`state_category` 与原版基础槽位元数据）；
- `states-summary.md`：供人类审查；
- `country-tags.json` / `country-tags-summary.md`：独立的国家 tag 注册、definition/history 存在状态与文件校验元数据（D-20260812-016）；
- 不复制 `history/states/*.txt` 或任何国家脚本正文。

导出命令：

```text
python3 scripts/workflow.py snapshot-export
```

Windows 使用 `py -3 scripts/workflow.py snapshot-export`。

独立国家 tag 快照使用：

```text
python3 scripts/workflow.py country-snapshot-export
```

Windows 使用 `py -3 scripts/workflow.py country-snapshot-export`。该命令与州快照相互独立，不改变州快照 schema 或环境能力布尔值。

如果环境检查发现本体指纹与已提交快照不一致，相关执行和加载测试必须停止，直到主调度器审查并提交新快照。
