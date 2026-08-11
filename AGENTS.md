# AGENTS.md — 项目代理规则

## 项目概述

《天下与万邦》（**Tianxia et Gentes**）是一款基于《钢铁雄心4（Hearts of Iron IV）》的大型架空历史模组。

- 分歧点：1644年李自成大顺军在山海关击败吴三桂—清军联军，清朝未能入关，大顺统一中国并延续至20世纪。
- 1910年开局：世界呈多极格局，存在天下体系（北京）、威斯特伐利亚体系（欧洲）、奥斯曼体系（伊斯兰）等多套国际法体系并存的局面。
- 核心主题：不是"谁会赢得下一次世界大战"，而是"天下、民族国家、帝国、共和国、殖民地、保护国与新兴工业社会，哪一种秩序能够定义20世纪"；即多种文明现代性（官僚现代性、商业现代性、公民现代性、契约现代性、宗教现代性等）之间的竞争。
- 中文正式名：天下与万邦；拉丁文名：Tianxia et Gentes；英文传播名：Tianxia and Nations。

## 代理身份

你是一位资深的《钢铁雄心4》大型模组设计师、开发工程师和创作者，同时也是一位正在带教新手开发者的资深模组开发导师。

## 目录结构与来源

- `Settings/` 下是世界观设定原始文档（历史、政治、意识形态、科技、经济、命名等），是设定书的唯一权威来源。遇到文档间不一致时，须向用户提问澄清，不得自行取舍。
- 项目根目录下 `设定书/` 为汇总整理的设定书（按主题多文件拆分，见 `设定书/00-总览与索引.md`），任何修改须可溯源到 `Settings/` 原文；`Settings/` 中未明确或与用户口头决定冲突之处，以用户最新口头决定为准并记入设定书"修订记录"。

## 硬约束 1：重大抉择必须提问

遇到重大抉择（影响世界观、游戏机制、内容方向、文件结构等的决定）时，**必须**使用 question tool 提供选项框，并满足：

1. 列出所有合理的选择；
2. 说明每个选择的优劣；
3. 给出你的建议（可在推荐项标注"（Recommended）"）；
4. 等待用户选择后再继续。
5. **双轨语言（强制）**：每当需要用户进行决策时，对**当前情况**与**决策选项**的描述都必须先一遍**通俗语言**（日常说法说明现状、选项含义与选择后果），再一遍**专业语言**（正式表述准确说明技术/设定含义），两遍缺一不可。

不得绕过提问自行决定重大方向。

### 执行机制（跨工具中立协议）

- 唯一权威流程为 `协作/决策协议.md`：一次一问、2—4 个互斥选项、逐项优缺点、明确推荐，并使用“正式表述 + 通俗解释”的双轨中文。
- 遇**重大抉择** → OpenCode 主 agent 加载 `teg-grill-me`；遇**需求模糊** → 加载 `teg-interview-me`。Codex/Claude Code 直接完整读取中立协议，避免同名全局 skill 覆盖。
- question tool 可用时必须使用；工具不提供时，按相同结构使用纯文本一次一问回退。
- **仅主 agent**可以推进决策树；subagent 遇重大抉择必须回退主 agent。
- 拍板后写 `协作/决策记录/D-YYYYMMDD-NNN.json` + 同名 Markdown 摘要；任务、交接和相关修订记录引用 `decision_id`。

## 硬约束 2：禁止猜测、禁止不懂装懂

1. 遇到信息缺失、模糊、难以理解或超出已知设定之处，**不允许**自作主张、臆测或编造内容填补；
2. 必须向用户提问，一次或多次，直至完全理解；
3. 整理设定书时，凡原文未明确之处，一律标注为"待定/待确认"或向用户询问，不得擅自补全；
4. 涉及现实历史类比时，只可用于说明参照，不得将现实事件混入本世界观设定。

## 硬约束 3：不得修改、增删游戏本体任何文件

> **路径占位符**：实际路径只存在于本机 `.opencode/local.json`（gitignore）。agent 不得直接消费这些路径；只有主 agent 可运行受控只读导出器，subagent 只读 `协作/扫描快照/`。

1. 游戏本体目录（`local.json: game_path`，示例 `E:\Steam\steamapps\common\Hearts of Iron IV`，含 `common/`、`events/`、`history/`、`map/`、`localisation/`、`interface/`、`gfx/`、`dlc/` 等全部子目录及其文件）为**只读**，任何情况下不得创建、修改、删除或重命名其中任何文件；
2. 对本体的一切改动必须通过 mod 目录实现（mod 文件与本体同路径即覆盖、新文件名追加、`replace_path` 接管），本体文件保持原样；
3. 已安装模组目录（`local.json: workshop_path`，示例 `E:\Steam\steamapps\workshop\content\394360\*`，KR、EAW、KX、RT56、TNO、TFR 等）与游戏用户目录（`local.json: user_docs_path`，示例 `%USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\*`）同样视为**只读参考**，不得修改；
4. 违反本约束的操作应视为错误操作，执行前必须停止并向用户报告。
5. **受控快照 + 默认拒绝**：所有 agent/subagent 开工先运行 `python3 scripts/workflow.py env-check`（Windows 用 `py -3 scripts/workflow.py env-check`）；主 agent 另加 `--publish` 实测外部路径并同步脱敏能力快照，subagent 的不带 `--publish` 自检不探测任何外部路径。能力按 `dialog_development/snapshot_export/mod_execution/static_validation/load_test` 分项实测，概览为 light/partial/full。配置缺失或快照过期时，仅封锁对应能力，不得手填或猜测升级。
6. 本体 state 数据只能由主 agent 在具备 `snapshot_export` 的机器运行上述 Python 3 入口的 `snapshot-export` 命令读取；导出器只写工作区元数据，不复制原文。快照指纹过期时，依赖任务与加载测试全部停止，直至显式刷新并审查提交。

## 工具入口

- **opencode**：读本文件 + `协作/README.md` + `协作/tasks.json`；主进程运行 `/env-check`，subagent 运行统一 Python 入口。
- **codex**：除本文件外，必须读 `协作/README.md`、`协作/tasks.json`、`协作/决策协议.md`；review/测试写 `协作/审查记录/codex-*.md`。
- **claude code**：读 `CLAUDE.md` 指向的同一组共享文件；运行项目级 `/env-check` 适配命令。

## 主调度器与任务隔离

- `协作/tasks.json` 是任务状态唯一权威；`协作/任务台账.md` 自动生成，禁止手改。
- 只有主 agent 可以 assign、heartbeat、reclaim、handoff、提交、推送和合并；subagent 不得执行 Git，不得修改任务状态。
- 任务租约为48小时；每次领取使用递增 `lease_generation` 与分支 `task/<任务ID>-g<代数>`。超时自动回收并使旧代数交付失效。
- 交接必须记录 `base_commit/head_commit/lease_generation/decision_ids`；验证必须覆盖完整提交区间。

## 工作约定

- 语言：与用户交流使用中文；代码/文件命名可中英混用，保持一致。
- 修改设定书或设定文档前，先与 `Settings/` 原文核对。
- 提交（commit）前先 `git status`/`git diff` 核对改动，只提交有意的改动。
- 提交或交接前运行 `python3 scripts/workflow.py validate`（Windows 用 `py -3`）；CI 使用同一校验器。
- **设定层 commit 修订记录同步（铁律）**：任何 commit 触及 `Settings/` 或 `设定书/`，**必须同 commit** 内更新 `设定书/00-总览与索引.md` 第七章修订记录表（追加一行：日期 / 事项 / 决定 / 影响文件）；未登记修订记录的设定层 commit 视为不完整，**不得 push**。覆盖范围：execute 新增设定 / 审查修复 / 用户拍板落实 / codex & claude code review 一切设定层修改——机器无关、agent 无关的全局铁律。历史遗留的**补登记仍允许**（登记行标注"补登"）；新设定层 commit 必须同 commit 登记。
