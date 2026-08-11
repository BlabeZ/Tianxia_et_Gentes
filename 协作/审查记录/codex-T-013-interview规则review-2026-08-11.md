# Codex T-013 interview-me 规则审查（2026-08-11）

## 审查范围

- 任务：`T-013`，lease generation `1`
- 决策：`D-20260811-005`
- 基线：`0a2c33a231c3c1df2d4cc9814645b606fb122fee`
- 任务 head：`e91932b54db40aeb14d5fded0df9baeb4efbdc53`
- 交接单：`协作/交接单/T-013-g1.json`

## 结论

**静态审查通过。原最终 review 所列 interview-me 缺口已经全部补回，可以确认当前中立协议覆盖最初 grill-me/interview-me 的收束意见。**

## 逐项核对

1. 每次后续问题都必须附当前猜测与理由；首次假设必须给出置信度，低于约 70% 时说明缺失信息。
2. 最终重述由五字段扩为六字段，明确加入“为何现在（Why now）”，并保留不得省略的“不包含（Out of scope）”。
3. 约 95% 停止条件已改为可检查问题：“能否预测用户对接下来三个问题的反应”；多轮仍不能预测时报告基础信息缺失并请求退一步。
4. 对“可扩展、现代、稳健、干净架构、最佳实践、标准做法”等应然性回答，必须追问用户在无需向任何人证明时真正想要什么。
5. `whatever you think`、`sounds good`、`sure, let's go` 和沉默后要求开工均被明确列为弱确认，不能触发终态；用户修订后必须重新完成六字段重述并取得明确确认。
6. 重大决策的 2—4 互斥选项流程与模糊需求访谈已分节：前者用于拍板具体权衡，后者默认使用可自由纠正、附猜测的一次一问，消除了“所有模糊问题都先给选项”与原 interview-me 收窄式访谈之间的冲突。
7. `teg-interview-me` 保持短适配器，唯一规则正文仍为 `协作/决策协议.md`，没有重新制造工具私有的第二份权威流程。

## 防回退门禁

`scripts/workflow.py` 固定检查上述规则的关键文本锚点，同时检查 namespaced skill 必须完整引用中立协议且保持短适配器。删除任一关键规则，或把完整流程重新复制进 skill，统一验证都会失败。

## 验证证据

- `python3 -m unittest discover -s tests -v`：41 项通过。
- 新增测试确认当前协议包含全部恢复规则，并能发现规则被删除或适配器膨胀。
- `python3 scripts/workflow.py validate`：通过。
- `python3 scripts/workflow.py validate --base 0a2c33a... --head e91932b...`：通过。
- 未修改 `Settings/` 或 `设定书/`，不触发设定层修订记录。
