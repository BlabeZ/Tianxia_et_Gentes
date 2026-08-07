# AGENTS.md — 项目代理规则

## 项目概述

《天下与万邦》（**Tianxia et Gentes**）是一款基于《钢铁雄心4（Hearts of Iron IV）》的大型架空历史模组。

- 分歧点：1644年李自成大顺军在山海关击败吴三桂—清军联军，清朝未能入关，大顺统一中国并延续至20世纪。
- 1910年开局：世界呈多极格局，存在天下体系（北京）、威斯特伐利亚体系（欧洲）、奥斯曼体系（伊斯兰）等多套国际法体系并存的局面。
- 核心主题：不是"谁会赢得下一次世界大战"，而是"天下、民族国家、帝国、共和国、殖民地、保护国与新兴工业社会，哪一种秩序能够定义20世纪"；即多种文明现代性（官僚现代性、商业现代性、公民现代性、契约现代性、宗教现代性等）之间的竞争。
- 中文正式名：天下与万邦；拉丁文名：Tianxia et Gentes；英文传播名：Tianxia and Nations。

## 目录结构与来源

- `Settings/` 下是世界观设定原始文档（历史、政治、意识形态、科技、经济、命名等），是设定书的唯一权威来源。遇到文档间不一致时，须向用户提问澄清，不得自行取舍。
- 项目根目录下 `设定书/` 为汇总整理的设定书（按主题多文件拆分，见 `设定书/00-总览与索引.md`），任何修改须可溯源到 `Settings/` 原文；`Settings/` 中未明确或与用户口头决定冲突之处，以用户最新口头决定为准并记入设定书"修订记录"。

## 硬约束 1：重大抉择必须提问

遇到重大抉择（影响世界观、游戏机制、内容方向、文件结构等的决定）时，**必须**使用 question tool 提供选项框，并满足：

1. 列出所有合理的选择；
2. 说明每个选择的优劣；
3. 给出你的建议（可在推荐项标注"（Recommended）"）；
4. 等待用户选择后再继续。

不得绕过提问自行决定重大方向。

### 执行机制（主 agent 挂钩 skills）

- 遇**重大抉择**（世界观 / 游戏机制 / 内容方向 / 文件结构）→ 加载 `grill-me` skill：用 question tool 一次一问、遍历决策树每个分支（2–4 选项 + 建议），系统性收束至拍板。
- 遇**需求模糊 / 拍板项方向未明**（如界线细化、领导人清单、资源 / 意识形态分布等前置缺口）→ 加载 `interview-me` skill：一问一答带猜测，收束至 95% 置信度再拍板。
- **仅主 agent**（opencode / codex / claude code 主进程）触发上述 skill；subagent 遇重大抉择不得自决，回退主 agent（见 `协作/README.md` 交接协议）。
- `grill-me`/`interview-me` skill 为**项目资产**（`.opencode/skills/`，随 git 分发，全机共享）；若本机缺文件，回退使用等效的一次一问流程（question tool 逐问+猜测）。

## 硬约束 2：禁止猜测、禁止不懂装懂

1. 遇到信息缺失、模糊、难以理解或超出已知设定之处，**不允许**自作主张、臆测或编造内容填补；
2. 必须向用户提问，一次或多次，直至完全理解；
3. 整理设定书时，凡原文未明确之处，一律标注为"待定/待确认"或向用户询问，不得擅自补全；
4. 涉及现实历史类比时，只可用于说明参照，不得将现实事件混入本世界观设定。

## 硬约束 3：不得修改、增删游戏本体任何文件

> **路径占位符（2026-08-05 重构）**：以下路径为示例占位；**实际路径以本机 `.opencode/local.json` 的 `game_path`/`workshop_path`/`user_docs_path` 字段为准**（该文件 gitignore，不入库，每台机器本地配置）。三种 agent 启动时先读 `.opencode/local.json` 确认本机能力档（全功能机/轻量机）。

1. 游戏本体目录（`local.json: game_path`，示例 `E:\Steam\steamapps\common\Hearts of Iron IV`，含 `common/`、`events/`、`history/`、`map/`、`localisation/`、`interface/`、`gfx/`、`dlc/` 等全部子目录及其文件）为**只读**，任何情况下不得创建、修改、删除或重命名其中任何文件；
2. 对本体的一切改动必须通过 mod 目录实现（mod 文件与本体同路径即覆盖、新文件名追加、`replace_path` 接管），本体文件保持原样；
3. 已安装模组目录（`local.json: workshop_path`，示例 `E:\Steam\steamapps\workshop\content\394360\*`，KR、EAW、KX、RT56、TNO、TFR 等）与游戏用户目录（`local.json: user_docs_path`，示例 `%USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\*`）同样视为**只读参考**，不得修改；
4. 违反本约束的操作应视为错误操作，执行前必须停止并向用户报告。
5. **多机能力档（二分模型 + 默认拒绝）**：无游戏本体的机器（如 Ubuntu，`capability_mode: light`）封锁长程自动化与测试，仅逐轮对话式开发；扫描产出经 git 共享（`协作/扫描产出.md`），测试由用户手动中继到全功能机。**默认拒绝**：`.opencode/local.json` 缺失/无效/`game_path` 不可达 → 一律判 light，不得未经用户显式确认自动升级能力。能力判定与开工许可由 `/env-check` command 执行（所有 agent/subagent 开工前必跑）。机器特定路径模板见 `.opencode/local.example.json`（共享），本机实际配置见 `.opencode/local.json`（gitignore）。

## 工具入口

- **opencode**：读 `AGENTS.md`（本文件）+ `协作/README.md` + `协作/任务台账.md`；subagent 配置在 `.opencode/agent/`；开工跑 `/env-check`。
- **codex**：读 `AGENTS.md`（codex 默认读取）；review/测试产出写 `协作/审查记录/codex-*.md`。
- **claude code**：读 `CLAUDE.md`（根目录入口，指向本文件+协作层）；debug/review 产出写 `协作/审查记录/cc-*.md`。

## 工作约定

- 语言：与用户交流使用中文；代码/文件命名可中英混用，保持一致。
- 修改设定书或设定文档前，先与 `Settings/` 原文核对。
- 提交（commit）前先 `git status`/`git diff` 核对改动，只提交有意的改动。
- **设定层 commit 修订记录同步（铁律）**：任何 commit 触及 `Settings/` 或 `设定书/`，**必须同 commit** 内更新 `设定书/00-总览与索引.md` 第七章修订记录表（追加一行：日期 / 事项 / 决定 / 影响文件）；未登记修订记录的设定层 commit 视为不完整，**不得 push**。覆盖范围：execute 新增设定 / 审查修复 / 用户拍板落实 / codex & claude code review 一切设定层修改——机器无关、agent 无关的全局铁律。历史遗留的**补登记仍允许**（登记行标注"补登"）；新设定层 commit 必须同 commit 登记。
