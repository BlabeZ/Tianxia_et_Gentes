# 15-KR中欧同盟GUI专题（Mitteleuropa 精读）

> 适用：经济圈/联盟的自定义复杂 GUI 面板（成员列表 + 投票/投资系统 + 前三排名 + 支持者视图）、隐藏按钮 tooltip 技巧、AI 操作 GUI。
> 参考样本：Kaiserreich（KR，`E:\Steam\steamapps\workshop\content\394360\1521695605`）的**中欧同盟（Mitteleuropa）**特殊 GUI——帝国公约（Reichspakt）阵营内部的德国主导经济圈面板。
> **姊妹篇**：[14-KR阵营页面与按钮机制.md](14-KR阵营页面与按钮机制.md)（阵营页面整体）；本专题深挖 KR 最复杂的一个自定义 GUI 面板。

## 一、机制定位：中欧同盟是什么

中欧同盟 = 德国主导的**经济圈**（economic sphere），成员 = 帝国公约核心国 + 德国附庸。玩家通过 GUI 面板进行**议程投票与投资**：每个"议程"（agenda，如工业项目/军备/基建/金融救助/法律改革）是一个可投票支持的项目，支持国投入政治点数（PP）提升议程分数，得分前三的议程获得全圈生效的奖励（idea），并可发起"领导权挑战"更换主席国。

**数据模型（三层）**：
```
经济圈：character 容器（MIT），成员存 MIT.economic_sphere:members 数组
议程：  角色对象（character），存 global.MIT_agendas 数组
        每个议程含：agenda_supporters（支持国数组）、agenda_score（分数变量）、
                   frame@国家（支持状态帧：2=支持 未设=不支持）
主席国：MIT（动态 tag，挑战成功则更替）
开关：  国家 flag mitteleuropa_window_open（面板开/关）+ 全局 dirty 变量 global.MIT_update
```

## 二、窗口层：gui_mitteleuropa.gui（542 行精读）

文件：`interface/kaiserreich/gui_mitteleuropa.gui`。开头用 `@` 常量统一尺寸：
```pdx
@window_width = 850
@agenda_entry_width = 336  @agenda_entry_height = 35
@top_agenda_width = 145   @top_agenda_height = 230
@member_entry_width = 52  @member_entry_height = 38
```

### 1. 打开按钮（`mitteleuropa_open_button_window`，77×77）
- 挂在主窗口外的小按钮（位置 x=0 y=-115），贴图 `GFX_idea_ger_revive_the_kaiserreich`；
- 带 `pdx_tooltip` + `pdx_tooltip_delayed`（普通/延迟提示两级）、`clicksound = click_ok`、`oversound = ui_menu_over`。

### 2. 主窗口（`mitteleuropa_window`，850×530）
```
mitteleuropa_window（moveable + click_to_front + 动画 decelerated 300ms，hide_position 滑出）
├── header_bg + title（mitteleuropa_title，hoi_36header）
├── button_close（ESC 关闭）
├── chairman_container（主席国区：chairman_flag 国旗 + large_flag_frame，tooltip 领袖说明）
├── next_election_container（下次选举：标题 + 值，含 tooltip）
├── countries_list（成员列表 558×175，verticalScrollbar）
│   └── countries_list_grid（网格 10 列 × 52×38，add_horizontal）
├── agenda_score（议程分数区 132×70）
│   ├── agenda_score_title + agenda_score_value（[GetMitteleuropaAgendaScore] scripted_loc）
│   ├── agenda_score_increase_button（GFX_extended_country_button frame=2 向上箭头）
│   └── agenda_score_decrease_button（frame=1 向下箭头）
├── top_agendas_container（前三名 405×230：三个并列背景 + top_agendas_grid 3 列）
├── agenda_list（议程列表 363×230，verticalScrollbar）
│   └── agenda_list_grid（agenda_entry 336×35 单列）
└── 3 个隐藏按钮（见第四节技巧）
```

### 3. 四个条目容器
| 容器 | 内容 |
|---|---|
| `member_entry`（52×38） | 成员国旗（GFX_flag_small2 + diplo_countrylist_flag_frame，tooltip 两级） |
| `agenda_entry`（336×35） | agenda_button（整行按钮）+ agenda_checkbox（复选框，动态 frame）+ name + score（右侧分数） |
| `top_agenda_entry`（145×230） | top_agenda_name + top_agenda_icon（动态图标）+ 主要支持国国旗 + supporters_list_grid（7×3 小旗网格）+ top_agenda_score |
| `top_agenda_supporter_entry`（25×25） | 支持国小旗（GFX_flag_smallest） |

## 三、scripted_gui 逻辑层：germany_mitteleuropa.txt（553 行精读）

文件：`common/scripted_guis/germany_mitteleuropa.txt`。两个 scripted_gui。

### 1. `mitteleuropa_button`（打开按钮逻辑）
```pdx
mitteleuropa_button = {
	parent_window_name = raid_filter          # 挂载点：raid 过滤器（地图顶栏旁）
	context_type = player_context
	window_name = "mitteleuropa_open_button_window"
	dirty = global.MIT_update                  # 重绘触发器

	visible = { GER_is_in_mitteleuropa = yes }  # 仅中欧成员可见

	ai_enabled = { always = yes }               # AI 也能开关面板
	ai_check = { MIT_interface_is_open = no }
	ai_test_interval = 168                      # 每 7-14 天 AI 决策一次

	triggers = {
		mitteleuropa_open_button_click_enabled = {
			MIT_is_active = yes
			NOT = { has_global_flag = MIT_event_chain_ongoing }   # 事件链进行中禁用
		}
	}

	effects = {
		mitteleuropa_open_button_click = {
			if = {
				limit = { MIT_interface_is_open = no }
				if = {  # 首次打开 → 引导事件
					limit = { is_ai = no NOT = { has_country_flag = MIT_opened_panel_once } }
					country_event = germany_mitteleuropa_events.1001
				}
				else = { MIT_open_mitteleuropa_panel = yes }
			}
			else = { MIT_close_mitteleuropa_panel = yes }   # 再点关闭
		}
	}
	ai_weights = { mitteleuropa_open_button_click = { ai_will_do = { base = 100 } } }
}
```

### 2. `mitteleuropa_window`（主面板逻辑）
- **visible**：`MIT_interface_is_open = yes`（= has_country_flag mitteleuropa_window_open）；
- **ai_enabled**：`ai_check = { GER_is_in_mitteleuropa = yes }`、`ai_test_interval = 240` + `ai_test_variance = 1`（±50% → 5-15 天随机间隔）；
- **dynamic_lists**（4 组数据驱动列表）：
```pdx
countries_list_grid = { array = MIT.economic_sphere:members  entry_container = member_entry  change_scope = yes }
agenda_list_grid = { array = MIT_agenda_list_for_ui  entry_container = agenda_entry  value = agenda
	ai_weights = { agenda_button_click = { ai_will_do = { ... 30+ 条 modifier 条件加权 ... } } } }
top_agendas_grid = { array = global.MIT_sorted_voted_agendas  entry_container = top_agenda_entry  value = top_agenda }
supporters_list_grid = { array = top_agenda:agenda_supporters  entry_container = top_agenda_supporter_entry  change_scope = yes }
```
（agenda_list_grid 内嵌**完整 AI 投票决策树**：战争对象不加、领导权挑战冷却、非大国不挑战、支持率/工厂比/议程类型加权等 30+ modifier——AI 与玩家共用同一按钮与逻辑。）

- **triggers**（按钮可用性，四档投资额）：
```pdx
agenda_score_increase_button_click_enabled = {
	set_temp_variable = { MIT_value = @MIT_small_value }    # 1 点
	MIT_has_political_power_for_investment = yes            # PP 足够检查
}
# control_click = 5、shift_click = 10、control_shift_click = 50
# 减少侧同构，检查 MIT_can_recover_political_power_investment
agenda_button_click_enabled = {  # 投票冷却检查
	if = { limit = { has_country_flag = MIT_recent_agenda_change }
		custom_override_tooltip = { tooltip = MIT_recent_agenda_change always = no } }
}
```

- **effects**（按钮点击效果）：
```pdx
agenda_score_increase_button_click = {
	set_temp_variable = { MIT_value = @MIT_small_value }
	MIT_add_agenda_score = yes
	MIT_recalculate_agenda_score_if_appropriate = yes
}
# 4 个档位 × 加/减 = 8 个按钮 + 2 个 tooltip 隐藏按钮 + 1 个 breakdown 按钮

agenda_button_click = {   # 支持/取消支持议程（最复杂逻辑）
	if = { limit = { NOT = { has_variable = MIT_supported_agenda } }
		var:agenda = { MIT_support_agenda = yes }
		MIT_apply_voting_cooldown = yes }           # 30 天冷却
	else_if = { limit = { check_variable = { MIT_supported_agenda = agenda } }
		# 若你是领导权挑战发起者 → 取消并全局清理挑战
		# 若你是专属议程发起者且无他人支持 → 移交领导权给随机支持者
		# 否则 → 取消支持
		var:MIT_supported_agenda = { MIT_stop_supporting_agenda = yes } }
	else = { # 换支持目标
		var:MIT_supported_agenda = { MIT_stop_supporting_agenda = yes }
		var:agenda = { MIT_support_agenda = yes }
		MIT_apply_voting_cooldown = yes }
	MIT_recalculate_all_agenda_scores = yes
	MIT_resort_agendas_based_on_score = yes
	MIT_update_gui = yes
}
agenda_reward_loc_button_click = { MIT_add_agenda_reward = yes  custom_effect_tooltip = SEPARATION_LINE  MIT_get_agenda_desc = yes }
top_agenda_reward_loc_button_click = { set_temp_variable = { agenda = top_agenda }  MIT_add_agenda_reward = yes }
agenda_score_breakdown_button_click = { MIT_get_agenda_score_breakdown = yes }
```

- **properties**（动态显示）：
```pdx
chairman_flag = { image = "[MIT.GetFlag]" }               # 主席国国旗（MIT 动态 tag）
member_flag = { image = "[THIS.GetFlag]" }                # 成员国旗
agenda_checkbox = { frame = agenda:frame@ROOT }           # 支持状态帧（2=支持）
top_agenda_icon = { image = "[GetMitteleuropaAgendaIcon]" }          # scripted_loc 动态图标
main_agenda_supporter_flag = { image = "[GetMitteleuropaMainSupporterFlag]" }
supporter_flag = { image = "[THIS.GetFlag]" }
```

## 四、隐藏按钮 tooltip 技巧（本面板最值得学的点）

窗口末尾有 3 个 `hide = yes` 的隐藏按钮：
```pdx
### this is a hidden button used to create scripted loc for MIT_add_agenda_reward, used in the agenda list container
buttonType = { name = "agenda_reward_loc_button"  spriteType = "GFX_name_list_item_bg"  hide = yes }
### 同构：top_agenda_reward_loc_button / agenda_score_breakdown_button
```
**原理**：scripted_gui 的按钮 effects 即使隐藏也会被引擎评估，因此隐藏按钮 = "在 GUI 评估时机执行脚本效果"的钩子。此处用于在每次 GUI 刷新时执行 `MIT_add_agenda_reward`/`MIT_get_agenda_desc`/`MIT_get_agenda_score_breakdown`——这些效果内部用 `meta_effect` 动态拼接文本与 idea 名，为议程条目生成动态 tooltip 文本（`custom_effect_tooltip`）。**即：tooltip 不是静态本地化，而是脚本在 GUI 评估时实时生成的**。

## 五、脚本端：MIT effects（1117 行，60 个顶层 effect）

文件：`common/scripted_effects/MIT effects (Mitteleuropa).txt`。

### 1. 面板开关（flag + dirty）
```pdx
MIT_open_mitteleuropa_panel = {
	if = { limit = { MIT_interface_is_open = no }
		hidden_effect = { MIT_update_agenda_list = yes }
		set_country_flag = mitteleuropa_window_open
		MIT_update_gui = yes } }
MIT_close_mitteleuropa_panel = {
	if = { limit = { MIT_interface_is_open = yes }
		clr_country_flag = mitteleuropa_window_open
		clear_array = MIT_agenda_list_for_ui
		MIT_update_gui = yes } }
MIT_update_gui = { set_variable_to_random = global.MIT_update }   # dirty 重绘核心
```

### 2. 议程投资（PP 成本计算）
```pdx
MIT_add_agenda_score = {
	set_temp_variable = { MIT_value_tooltip = MIT_value }
	add_to_variable = { MIT_agenda_investment = MIT_value }
	set_temp_variable = { MIT_cost = {
		value = MIT_value  multiply = -1
		multiply = { value = 1  add = modifier@mitteleuropa_investment_cost  clamp = { min = 0.1 max = 2 } } } }
	hidden_effect = { add_political_power = var:MIT_cost }   # 扣 PP
	MIT_update_gui = yes
	custom_effect_tooltip = MIT_add_agenda_score_tooltip }
```
（投资额 1/5/10/50 × 成本系数 [1 + mitteleuropa_investment_cost]，clamp 0.1-2；subtract 侧反向退还并 clamp ≥0。**投资额 = 玩家对议程的"投票强度"**。）

### 3. 支持议程（数组 + 帧 + 引用）
```pdx
#on agenda character scope - PREV must be a country
MIT_support_agenda = {
	add_to_array = { agenda_supporters = PREV }
	set_variable = { frame@PREV = 2 }              # GUI 复选框帧
	set_variable = { PREV.MIT_supported_agenda = THIS } }
MIT_stop_supporting_agenda = {
	remove_from_array = { agenda_supporters = PREV }
	clear_variable = frame@PREV
	clear_variable = PREV.MIT_supported_agenda }
MIT_set_as_agenda_leader = { ... }   # 移交领导权
```

### 4. 议程分数计算（mtth 权重）
```pdx
MIT_recalculate_agenda_score = { #on agenda scope
	clear_variable = agenda_score
	if = { limit = { check_variable = { agenda_supporters^num > 0 } }
		for_each_scope_loop = { array = agenda_supporters
			add_to_variable = { PREV.agenda_score = mtth:mitteleuropa_agenda_score_calculation } } }
	MIT_update_gui = yes }
```
（`mtth:mitteleuropa_agenda_score_calculation` 定义在 `common/mtth/GER_mtth.txt`——每个支持国按自身条件（工厂数/战争状态等）计算对议程分数的贡献权重，即"支持国实力决定投票权重"。）

### 5. 议程奖励（meta_effect 动态名拼接）
```pdx
MIT_add_agenda_reward = {
	if = { limit = { var:agenda = { has_character_flag = MIT_has_unique_agenda_effect } }
		meta_effect = { text = { [AGENDA_IDEA]_idea_effect = yes }  AGENDA_IDEA = "[?agenda.GetName]" } }
	else = {
		meta_effect = { text = { add_timed_idea = { idea = [AGENDA_IDEA] days = 180 } }
			AGENDA_IDEA = "[?agenda.GetName]_idea" } } }
```
（普通议程 → 180 天限时 idea `议程名_idea`；有专属效果的议程 → 调用 `议程名_idea_effect` 脚本。**奖励完全由议程名动态驱动**，新增议程只需建角色+写效果，无需改 GUI。）

### 6. 加入/退出中欧（经济圈 + 制度叠加）
```pdx
GER_add_to_mitteleuropa = {
	if = { limit = { GER_is_in_mitteleuropa = no }
		set_country_flag = MIT_was_in_mitteleuropa
		add_dynamic_modifier = { modifier = MIT_mitteleuropa_modifier }
		set_temp_variable = { sphere_target = THIS }
		MIT = { add_to_economic_sphere = yes }    # 复用通用经济圈系统
		hidden_effect = { ...按德国已完成国策叠加制度 modifier：
			GER_directive_system → MIT_add_directive_system_modifiers
			GER_mitteleuropa_court → MIT_add_court_system_modifiers
			GER_berlin_bureaucracy → add_ideas = MIT_berlin_bureaucracy
			MIT_europamark_in_effect → 事件 1009 ... } } }
```

### 7. 其他关键 effect
`MIT_challenge_leadership_idea_effect`（发起领导权挑战，触发议程投票）、`MIT_set_new_chairman`（主席国变更 + 广播）、`MIT_resort_agendas_based_on_score`（按分数排序填 `global.MIT_sorted_voted_agendas`）、`MIT_update_agenda_list`（填 `MIT_agenda_list_for_ui`）、`MIT_unlock_agenda_for_country`（国家专属议程解锁）、`MIT_enlargement_directorate_*`（扩大总署：吸收新成员）。

## 六、触发与判定（MIT triggers）

文件：`common/scripted_triggers/MIT triggers (Mitteleuropa).txt`（5 个顶层 trigger）：
```pdx
MIT_is_active = { custom_override_tooltip = { tooltip = MIT_is_active
	GER = { has_country_flag = MIT_election } } }        # 中欧机制已启用
MIT_is_current_president = { custom_override_tooltip = { tooltip = MIT_is_current_president  tag = MIT } }
MIT_interface_is_open = { has_country_flag = mitteleuropa_window_open }
MIT_has_political_power_for_investment = {   # PP 检查 × 成本系数
	multiply_temp_variable = { MIT_value = { value = 1  add = modifier@mitteleuropa_investment_cost  clamp = { min = 0.1 max = 2 } } }
	NOT = { check_variable = { political_power < MIT_value } } }
MIT_can_recover_political_power_investment = { ... }  # 回收检查
```

## 七、scripted_localisation（动态文本）

文件：`common/scripted_localisation/MIT scripted_loc (Mitteleuropa).txt`（12 个 defined_text）：
- `GetMitteleuropaAgendaScore`（GUI 分数显示）、`GetMitteleuropaAgendaIcon`（议程图标）、`GetMitteleuropaMainSupporterFlag`（主要支持国国旗）、`GetMitteleuropaNextElectionValue` 等——按议程角色变量/flag 查表返回文本或贴图名，供 GUI properties/text 引用。

## 八、事件链（改革事件）

`events/MIT events (Mitteleuropa).txt`（1296 行）：
- `germany_mitteleuropa_events.1001`：**首次打开面板引导事件**（`set_country_flag = MIT_opened_panel_once` + `MIT_open_mitteleuropa_panel`），即 scripted_gui 按钮里首次点击触发的事件；
- `1002+`：各制度改革事件（指令体系/协商大会/合格多数/预算配额/欧洲马克/央行……），事件内 `every_subject_country` 广播给全体中欧成员。

## 九、实现链路总览（中欧 GUI 全流程）

```
玩家点打开按钮（mitteleuropa_button，visible=GER_is_in_mitteleuropa）
  → 首次：事件 1001 引导；否则 MIT_open_mitteleuropa_panel
  → set_country_flag mitteleuropa_window_open + MIT_update_agenda_list + dirty
  → scripted_gui mitteleuropa_window visible=true
  → dynamic_lists 渲染 4 个列表（成员/议程/前三/支持者）
  → 玩家点议程 +/− 按钮（1/5/10/50 点）
     → triggers 查 PP 足够（含成本系数）
     → MIT_add/subtract_agenda_score（改 MIT_agenda_investment + 扣/退 PP + dirty）
     → MIT_recalculate_agenda_score（各支持国 mtth 权重求和）
  → 玩家点 agenda_button 支持/换/取消（30 天冷却，挑战逻辑特殊处理）
     → MIT_support/stop_supporting_agenda（数组+帧+引用）
     → 重算全部分数 + 排序 + dirty
  → 前三名 top_agenda_entry 显示 + 支持者国旗网格
  → 每次 GUI 评估执行隐藏按钮 → MIT_add_agenda_reward 动态生成 tooltip/奖励
  → 议程到期/达成 → 全圈广播改革事件（1002+）或限时 idea 生效
  → AI 通过 ai_enabled/ai_weights 参与全部流程（投票/支持/开关面板）
```

## 十、对本项目的借鉴清单

| 中欧 GUI 机制 | 本 mod 对应需求 | 移植要点 |
|---|---|---|
| 经济圈 + 角色议程对象 | 天下体系"朝贡议程/共同事业" | 议程=角色存数组；支持=数组+frame+引用三件套 |
| 四档投资按钮（1/5/10/50 × 成本系数） | 任何"投入资源投票/投资"系统 | `@` 常量 + triggers 预检 + MIT_add_agenda_score 模式 |
| mtth 权重计分 | 成员实力加权投票 | `mtth:xxx_calculation` 复用 |
| meta_effect 动态奖励名 | 可扩展议程库 | `[AGENDA_IDEA]_idea` 动态拼接 + 专属 flag 分流 |
| **隐藏按钮 tooltip 技巧** | 动态 tooltip 文本 | hide=yes 按钮 + effects 在 GUI 评估时执行 |
| dirty 变量重绘 | 一切面板刷新 | `MIT_update_gui = set_variable_to_random global.MIT_update` |
| AI 完整参与 GUI | 体系决策 AI 化 | ai_enabled + ai_check + ai_weights（30+ 条件决策树） |
| 引导事件 + 冷却 | 玩家上手与防刷 | 首次 flag + 事件 + 30 天投票冷却 |
| 国策→制度 modifier 叠加 | 体系改革制度 | GER_add_to_mitteleuropa 的 hidden_effect 模式 |

## 附：关键文件路径速查

| 文件 | 作用 |
|---|---|
| `interface/kaiserreich/gui_mitteleuropa.gui`（542 行） | 窗口层（打开按钮 + 主面板 + 4 条目容器 + 3 隐藏按钮） |
| `common/scripted_guis/germany_mitteleuropa.txt`（553 行） | scripted_gui 逻辑层（visible/triggers/effects/properties/dynamic_lists/ai） |
| `common/scripted_effects/MIT effects (Mitteleuropa).txt`（1117 行，60 effect） | 面板开关/投资/支持/计分/奖励/主席/加入退出 |
| `common/scripted_triggers/MIT triggers (Mitteleuropa).txt` | 5 个判定（active/open/PP 检查） |
| `common/scripted_localisation/MIT scripted_loc (Mitteleuropa).txt` | 12 个动态文本/图标 |
| `common/mtth/GER_mtth.txt` | `mitteleuropa_agenda_score_calculation` 投票权重 |
| `events/MIT events (Mitteleuropa).txt`（1296 行） | 引导事件 1001 + 制度改革事件 1002+ |
| `interface/kaiserreich/gui_mitteleuropa.gfx` | 中欧面板图标 |

> **扩展阅读**：本面板背后的**约 6 个月固定周期会议投票**（flag 计时 → MTTH 结算 → 三事件结算链 → 周期重置）、议程=角色对象体系、以及"议程→flag→国策→全员广播"的双向联动，见 [16-KR中欧同盟投票周期与国策联动.md](16-KR中欧同盟投票周期与国策联动.md)。
