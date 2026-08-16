# 14 hagane.works 工作台参考（社区工具）

> 来源：haganeworks/hoi4-modmaking-skills 开源仓库 v1.3.0（GitHub，2026-08-16 抓取），**CC BY-NC-SA 4.0**（非商业）。
> 原文：`grammar/_sources/hagane-field-reference/`（40 文件）+ `grammar/_sources/hagane-README.md`。
> 平台：https://scharnhorst.hagane.works（HOI4 模组可视化工作台，公测免费）。

## 1. 这是什么

- 社区开发的 **HOI4 模组可视化工作台**（浏览器）：国家/角色/国策树/事件/决议/民族精神/科技/州域/装备/部队/MIO/情报/特殊项目等可视化编辑器 + AI 联动（BYOK 自带 LLM key，模型无关）。
- 平台负责：ID 冲突自动后缀、命名空间自动前缀、**加载前校验**（export/validate + lint）、标准 mod 文件夹导出。
- 本目录收录的是它开源的 **field-reference（字段参考）**——HOI4 脚本词汇 ↔ 平台 API 字段的映射表，可作语法速查与核验参考。

## 2. 接入方式（MCP / Skills，官方提供）

- **MCP**（Option A，推荐）：Streamable-HTTP 服务器 `https://scharnhorst.hagane.works/mcp/`，认证 `Authorization: Bearer hoi4pat_令牌`（需注册账号生成 Personal Access Token）。
- **Skills**（Option B）：仓库 `skills/` 目录（SKILL.md 指令包）拷贝到 agent skills 目录 + `field-reference/` 作工作目录 + `platform.env` 存令牌。
- 命令百科 2420+ 条无需登录：`https://scharnhorst.hagane.works/zh/wiki`。

## 3. 对我们的定位（重要）

- **只作参考学习与语法核验**：field-reference 的 token 词汇表与官方 wiki 一致，可交叉印证（如 `check_variable` 完整 compare、`set_politics` 参数）。
- **不改变受控开发流程**：平台导出物不走本项目 validate/决策协议/受控快照体系；AGENTS.md 硬约束（本体只读、决策记录等）继续适用。
- 平台自身校验端点（export/validate、lint/tree-validation）作为额外语法检查手段可考虑，但依赖网络与账号，不作门禁。

## 4. 文件导读（grammar/_sources/hagane-field-reference/）

| 文件 | 内容 | 本项目相关度 |
| ---- | ---- | ---- |
| `tokens.md` | 共享 token 词汇速查（effects/triggers/modifiers/scopes 高信号清单） | ★★★ 最高频 |
| `_raw-script-fields.md` | 各工作台 raw-script 字段主清单 + 包装惯例 | ★★★ |
| `_validation-tools.md` | 只读校验端点（cross-ref/scripted-symbol/lint） | ★★ |
| `_timeline-and-replace-path.md` | 非 1936 开局/全转换 + 同名覆盖 vs replace_path 两机制 | ★★★（与 grammar/02、12 交叉印证） |
| `_editing-existing-mods.md` | 导入已有 mod 编辑/追加导出 | ★ |
| `ideologies.md` | 意识形态工作台字段（types/rules/modifiers/本地化/GFX） | ★★★（与 grammar/13 印证） |
| `opinion-modifiers.md` | 好感修改器字段（value/desc/自定义） | ★★★（T-046 直接相关） |
| `history-files.md` / `states.md` | 历史文件/州字段 | ★★★（T-045/T-041 相关） |
| `countries.md` / `events.md` / `focus.md` / `decisions.md` / `ideas.md` / `characters.md` | 各国策/事件/决策/精神/角色字段 | ★★（后续内容任务） |
| `scripted-snippets.md` / `scripted-localisations.md` / `dynamic-modifiers.md` / `modifier-definitions.md` | 脚本片段/脚本化本地化/动态修改器 | ★★ |
| `defines.md` | common/defines/*.lua 每键覆盖 + 开局日期红线 | ★（zz_txg_defines.lua 参考） |
| `wargoals.md` / `super-events.md` / `bookmarks.md` / `custom-traits.md` | 战争目标/超级事件/书签/自定义特质 | ★ |
| `technologies.md` / `equipment.md` / `sub-units.md` / `division-*.md` / `oob-units.md` / `mios.md` / `doctrines.md` / `special-projects.md` / `intelligence-agencies.md` / `autonomy-states.md` / `music.md` / `balance-of-power.md` / `peace-conference.md` / `ui-panels.md` | 军事/硬件/UI 各领域字段（部分 DLC 门槛或暂不建议） | ★（远期） |

## 5. tokens.md 精华摘录（速查）

**效果（effect 字段）**：
- 政治/经济：`add_political_power`、`add_stability`、`add_war_support`、`add_ideas`/`remove_ideas`/`swap_ideas`、`set_politics = { ruling_party = <四极> elections_allowed = yes }`、`set_party_name`、`add_popularity = { ideology = <组> popularity = 0.1 }`
- 外交：`add_to_faction`、`declare_war_on = { target = X type = annex_everything }`、`puppet`、`set_autonomy`（在宗主作用域、target=附庸）、`transfer_state`、`add_state_core`
- 科技/装备：`add_tech_bonus`（分类注意：construction/infrastructure 非科技类别，用 industry）、`set_technology`、`add_equipment_to_stockpile`
- 人物：`promote_character = { ideology = <子类型> }`、`create_country_leader`、`recruit_character`（仅历史文件）
- 变量/旗标：`set_country_flag`/`clr_country_flag`、`set_variable = { var = X value = 5 }`、`custom_effect_tooltip`（变量/旗标效果无自动 tooltip 需配）、`country_event = { id = X days = N }`

**触发器（condition 字段）**：
- `has_country_flag`、`check_variable = { var = X value = 5 compare = greater_than }`、`original_tag`、`has_government = <组>`、`date > 1936.6.1`、`has_completed_focus`、`has_idea`、`has_dlc`、`NOT/AND/OR`

**修改器（modifier 字段）**：
- `political_power_factor`、`stability_factor`、`research_speed_factor`、`production_speed_factor`、`consumer_goods_factor`、`army_org_factor`、`justify_war_goal_time`、`conscription`、`industrial_capacity_factory`

**作用域**：
- 国策/决策完成奖励：ROOT=执行国；定向决策：ROOT=执行者、FROM=当前目标；事件：ROOT=收件国、FROM=发送国
- 开作用域：`every_country = { limit = { ... } }`、`owner = { ... }`、`<TAG> = { ... }`、`event_target:<key>`

> 与官方 wiki（grammar/01-13）交叉印证：tokens 清单与 Effect/Triggers 页一致；平台 lint 是额外校验手段，最终门禁仍是游戏 error.log。
