# Codex T-012 state 受控转换审查（2026-08-11）

## 审查范围

- 任务：`T-012`，lease generation `1`
- 决策：`D-20260811-004`
- 基线：`f35616c1970ed867e0f228465674e2d141eb6046`
- 任务 head：`d4c463148d329c67460b1e109d7a24481566e904`
- 交接单：`协作/交接单/T-012-g1.json`

## 结论

**机器 C 范围内静态审查通过，可进入待合并。** 原 review 的“快照字段不足以重建完整 state、execute 又被要求直接改写完整文件”矛盾已在架构和代码层闭环：subagent 只产出声明式改写清单，真实本体只由具备能力的主 agent 通过固定 `state-build` 命令读取，完整结果直接写入 mod。

本结论不包含真实 HOI4 本体端到端通过。机器 C 没有 `snapshot_export/mod_execution/load_test`；真实文件兼容性、生成后的静态检查和游戏加载必须由 T-028 在快照为 `current` 的 full/partial 机完成。

## 安全与正确性核对

1. `scripts/state_transform.py` 是无本机路径知识的纯转换核心；未声明内容原样保留，只处理 Schema 支持的归属、控制者、核心、宣称、人口、州类别、资源和州级建筑字段。
2. `state-build` 的来源固定为本机私有 `game_path/history/states`，输出固定为工作区 `mod/history/states`；外部或绝对改写清单路径、输出目录解析越界均被拒绝。
3. 执行前同时要求 `snapshot_export=true`、`mod_execution=true` 和快照 `current`，并逐项核对总体指纹、state ID、相对路径与单文件 SHA-256。
4. 唯一字段重复、同一 state 被多份清单修改、路径越界、单行结构需要插入、输入编码无效或花括号不平衡时默认失败，不猜测修复。
5. 转换器先在内存中完成全部 state 校验，再写入 mod；现有目录若含快照之外的 `.txt` 文件会拒绝，不自动删除用户文件。
6. `.opencode/agent/execute.md` 已撤销 `mod/*` 写权限，只允许写 `协作/state-overrides/*` 和交接证据；T-020—T-027 的产出同步改为地域清单。
7. 新增 T-028 作为唯一汇总生成任务，依赖全部地域清单和经济/工业清单，并要求 `snapshot_export/mod_execution/static_validation`。
8. 未修改 `Settings/` 或 `设定书/`，没有新增世界观内容，不触发设定层修订记录。

## 验证证据

- `python3 -m unittest discover -s tests -v`：39 项通过，其中 14 项为 state 转换专项测试。
- 专项覆盖：字段保留/替换/删除、缺失资源与建筑块插入、重复唯一字段拒绝、state ID 拒绝、快照指纹拒绝、跨清单冲突拒绝、未知字段 Schema 拒绝、意外旧文件拒绝、light 机能力拒绝，以及模拟 current 快照的完整命令集成路径。
- `python3 scripts/workflow.py validate`：通过。
- `python3 scripts/workflow.py validate --base f35616c... --head d4c4631...`：通过。
- `python3 -m py_compile scripts/state_transform.py scripts/workflow.py tests/test_state_transform.py`：通过。
- 机器 C 直接调用 `state-build`：在读取清单和本体前按预期返回“不具备 snapshot_export”。

## T-028 必须完成的验收

- 在目标机重新运行 `env-check --publish` 并确认快照 `current`；
- 使用已提交的全部地域清单执行 `state-build`，审查完整生成差异；
- 运行统一静态校验，并将任务登记为需要加载测试；
- 完成真实 HOI4 加载测试后才能进入待合并，不能用本报告替代。
