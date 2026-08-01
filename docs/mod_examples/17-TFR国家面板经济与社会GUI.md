# 17-TFR国家面板经济与社会GUI（贸易页签经济面板 + 社会发展机制）

> 适用：**国家面板（贸易页签/顶栏）下的自定义经济 GUI**、经济类型图标系统、经济行动 token 系统（meta_effect 动态拼接）、贷款/还款按钮、社会发展变量机制。
> 参考样本：The Fire Rises（TFR，`E:\Steam\steamapps\workshop\content\394360\3350890356`）。
> **姊妹篇**：[13-TFR现代战争与宏观账本参考.md](13-TFR现代战争与宏观账本参考.md)（add_GDP 宏观账本内核）；本专题聚焦**UI 层**与**社会机制层**。

## 一、总览：国家面板下挂载的 GUI 群

TFR 的经济/社会 UI 由 4 组 scripted_gui + 对应窗口层组成，全部**复用原版窗口挂载点**（`trade_tab` 贸易页签、`top_bar` 顶栏、`ruling_party_wings_bg_anchor` 党翼锚点）：

| GUI | 挂载点 | 内容 |
|---|---|---|
| `money_container`/`money_debt_container`（窗口层） | 顶栏右上 | GDP 与债务实时数值显示 |
| `TFR_economy_button_container` | trade_tab | 经济面板开关按钮（frame 状态切换） |
| `econ_tab_window_gui` | trade_tab | **经济标签页主体**（类型图标/行动/贷款/投资） |
| `TFR_economy_ledger_gui_title` | trade_tab | 经济账本（全球/组织/阵营 GDP 排名） |
| `party_popularity_number` + `TFR_ruling_party_wings_GUI` | top_bar / 党翼锚点 | 政党支持率与执政党翼指示灯 |

"社会"部分**没有独立大面板**——社会发展（socdev）通过 6 项变量 + idea 阶梯 + 地图模式（贫困/疾病/文化）呈现。

## 二、顶栏金钱/债务显示（`interface/TFR_interface_economy.gui`）

```pdx
containerWindowType = {
	name = "money_container"
	position = { x = -655 y = 4 }   # Orientation = UPPER_RIGHT（顶栏右上）
	iconType = { name = "money_bg"  spriteType = "generic_box_125" }
	iconType = { name = "gdp_icon"  spriteType = "GFX_money2" }
	instantTextBoxType = {
		name = "money_text"
		font = "VCR02_14"
		text = "[Get_GDP_total]"        # ← scripted_loc 动态文本
		pdx_tooltip = "MONEY_TOOLTIP"   # 两级 tooltip
		pdx_tooltip_delayed = "MONEY_TOOLTIP_DESC"
	}
}
# money_debt_container 同构（GFX_money + [Get_DEBT]）
# 另有 small 变体（尺寸切换）与 money_element_size_button（可见性切换按钮）
# TFR_econ_gdp_gui_container：GDP 大字面板 + gdp_printer_button（Print Money 按钮）
```

要点：顶栏实时显示 GDP/债务（scripted_loc `[Get_GDP_total]`/`[Get_DEBT]`），含大小容器切换与 tooltip。

## 三、经济标签页：econ_tab_window_gui（`TFR_scripted_guis_ZZZ_economy.txt`，615 行）

### 1. 开关按钮（`TFR_economy_button_container`）
```pdx
effects = {
	open_econ_button_click = {
		if = { limit = { NOT = { has_country_flag = TFR_economy_tab_open } }
			set_country_flag = TFR_economy_tab_open
			set_variable = { open_econ_button_frame = 2 } }   # 按下态帧
		else_if = { ... clr_country_flag + frame = 1 ... }    # 弹起态帧
	}
}
properties = { open_econ_button = { frame = open_econ_button_frame } }
```
（flag 开关 + 帧变量驱动按钮按下/弹起视觉。注意：`econ_tab_window_gui` 的 visible 是 `NOT { has_country_flag = TFR_economy_tab_open }`——**面板默认显示，点按钮隐藏**，即"折叠"式设计。）

### 2. 经济类型图标系统（28 种 + 国际组织）
- **triggers**：`TFR_no_economy_type_icon_visible`（无任何类型 idea 时）→ `TFR_xxx_type_icon_visible`（逐个 28 种经济类型 idea：ZZZ_capitalist_economy/american_capitalism/collective_capitalism/oligopolistic_capitalism/cabal_economy/welfare_capitalism/corporatism/managed_economy/command_economy/planned_economy/socialist_market/developed_socialism/military_controlled_economy/worker_controlled_economy/chaostic_economy/minarchism/ancap/mixed_economy/party_state_capitalism/state_capitalism/america_first_capitalism/maga_capitalism/left_corporatism/liberal_corporatism/kaiser_economy/inclusive_capitalism…）；
- **国际组织图标**：`TFR_eu_econ_icon_visible`（`has_dynamic_modifier = { modifier = EU_member_dynamic }`）、`TFR_ads/tmc/brics/pec_econ_icon_visible`（`has_dynamic_modifier OR has_idea`）、`arab_league`/`asean`/`eec`——**经济类型与所属经济圈双图标显示**。

### 3. 经济行动 token 系统（meta_effect 动态拼接——本面板核心技巧）
```pdx
dynamic_lists = {
	economic_actions_gridbox = {
		array = economic_actions_array           # 开局填 4 个 token
		entry_container = economic_actions_window_item_grid
		value = economicaction
	}
}
effects = {
	action_button_click = {
		meta_effect = { text = { [TOKEN]_effect = yes }  TOKEN = "[?economicaction.GetTokenKey]" }
	}
	action_button_right_click = {
		meta_effect = { text = { custom_effect_tooltip = [TOKEN]_desc }  TOKEN = "[?economicaction.GetTokenKey]" }
	}
}
triggers = {
	action_button_click_enabled = {
		is_economic_action_trigger = yes
		meta_trigger = { text = { [TOKEN]_trigger = yes }  TOKEN = "[?economicaction.GetTokenKey]" }
	}
}
```
**原理**：按钮的 effect/trigger/tooltip 全部由 token 名动态拼接——新增经济行动只需：① 在 `economic_actions_array` 加 token；② 写 `<token>_effect`/`<token>_trigger`/`<token>_desc` 三个脚本。**GUI 零改动**。现有 4 个行动（`00_TFR_scripted_effects_ZZZ_economic_actions.txt` + `TFR_scripted_triggers_ZZZ_economic_actions.txt`）：
- `print_money_economic_action`（印钞：175 天限时 idea，PP≥100）
- `quantitative_tightening_economic_action`（量化紧缩）
- `war_taxes_economic_action`（战争税，需开战）
- `develop_state_economic_action`（开发州：13 级 state_category 升级链，700 天州冷却）

### 4. 自动还款 / 银行复选框
```pdx
properties = { auto_payment_checkbox = { frame = auto_payment_var } }
effects = {
	auto_payment_checkbox_click = {
		if = { limit = { has_country_flag = auto_payment_flag }
			set_variable = { var = auto_payment_var value = 1 }  clr_country_flag = auto_payment_flag }
		else = { set_country_flag = auto_payment_flag  set_variable = { var = auto_payment_var value = 2 } } }
}
# bank_checkbox 同构（bank_var / bank_flag）
```
（flag + 帧变量（1=关 2=开）驱动复选框视觉；`add_GDP` 中 `has_country_flag = auto_payment_flag` 决定盈余自动还债还是累积收入。）

### 5. 贷款 / 还款按钮（GDP 尺度）
```pdx
# 贷款：+收入、+1.5 倍债务（模拟借债成本）
gdp_1b_loan_button_click = {
	set_temp_variable = { var = income_var_temp value = 1 }
	add_income = yes
	set_temp_variable = { var = debt_var_temp value = 1.5 }
	add_debt = yes }
# 10b / 50b 同构（10/15、50/75）；还款按钮反向（-1/-1、-10/-10、-50/-50）
gdp_1b_loan_button_click_enabled = {
	has_disabled_ideas = yes
	NOT = { has_country_flag = auto_payment_flag } }   # 自动还款开启时禁手动贷款
```

### 6. 民用/军事投资按钮
```pdx
Economic_Civilian_Investments_Button_click = {
	add_timed_idea = { idea = generic_civilian_development_investments_idea  days = 120 } }
# 互斥：同时只能有一种投资 idea（triggers 检查）
```

### 7. AI 参与（ai_weights）
```pdx
ai_enabled = { has_content_tag = yes }
ai_test_interval = 720   # 每 30 天
ai_weights = {
	auto_payment_checkbox_click = { ai_will_do = {
		base = 0
		modifier = { add = 1 OR = {
			AND = { has_country_flag = auto_payment_flag  debt_difference_var < 0 }   # 盈余→开自动还债
			AND = { NOT = { has_country_flag = auto_payment_flag }  debt_difference_var > 0 } } } } }
	# bank_checkbox 同构
}
```
（AI 按收支差自动开关自动还款/银行。）

## 四、经济账本（`TFR_economy_ledger_gui_title`，scripted_gui 15695 字节 + 窗口 29KB）

- 挂在 trade_tab，`visible = { is_ai = no }`（仅玩家）；
- **6 个排序按钮** → 各触发三级计算：
```pdx
TFR_economy_ledger_button_one_click = {   # GDP 排序
	TFR_economic_ledger_calculation_gdp = yes
	TFR_economic_ledger_union_calculation_gdp = yes       # 国际组织聚合
	TFR_economic_ledger_faction_calculation_gdp = yes     # 阵营聚合
	TFR_economic_ledger_global_calculation_gdp = yes      # 全球聚合
	TFR_economic_ledger_faction_calculation_milspending = yes
	if = { limit = { NOT = { has_global_flag = econ_ledg_val_gdp } }
		set_global_flag = econ_ledg_val_gdp   # 切换显示指标
		clr_global_flag = econ_ledg_val_rgdp / debt / fctr / rsrc_p / rsrc_n } }
```
- 6 个显示指标：GDP / 实际 GDP / 债务 / 工厂 / 资源正 / 资源负（`econ_ledg_val_*` 全局 flag 互斥切换）；
- 数据来源：`TFR_scripted_effects_ZZZ_economy_ledger.txt`（73KB）用 `get_sorted_scored_countries` + 评分器（`economy_ledger_gdp_scorer` 等，定义于 `common/scorers/country/economy_ledger_scorers.txt`）+ 三级聚合（union 先 `random_country` 选代表 leader 再累加成员 GDP）。
- 窗口层：`interface/TFR_economy_ledger.gui`（28984 字节，含排序按钮条、各国条目列表）。

## 五、社会机制（无独立大面板，变量 + idea 阶梯 + 地图模式）

### 1. 6 项社会发展变量（`00_TFR_scripted_effects_ZZZ_generic.txt`）
```pdx
update_development = {   # on_monthly 每月执行（00_TFR_on_actions_ZZZ_development.txt）
	add_to_variable = { var = academic_development_var  value = modifier@academic_development_monthly }
	check_academic_development = yes
	# farming_development / poverty_development / industrial_development /
	# military_development / society_development 同构
}
```
**6 项发展**：学术/农业/贫困/工业/军事/社会——每项一个变量，月度按 modifier（`xxx_development_monthly`）累积。

### 2. 阈值检查 + idea 阶梯（check_*/increase_*/decrease_*）
```pdx
check_society_development = {
	if = { limit = { check_variable = { society_development_var >= 1 } }
		ROOT = { country_event = { id = generic.16 }  country_event = { id = generic.18 } }
		increase_society = yes
		add_to_variable = { society_development_var = -1 } }   # 消耗 1 点升级
	else_if = { limit = { society_development_var <= -1 }
		... decrease_society = yes ... }
}
increase_society = {   # idea 阶梯：lower→low→medium→high→higher→highest
	if = { limit = { has_idea = higher_society } swap_ideas = { remove_idea = higher_society add_idea = highest_society } }
	if = { limit = { has_idea = high_society } swap_ideas = { remove_idea = high_society add_idea = higher_society } }
	else_if = { limit = { has_idea = medium_society } swap_ideas = { remove_idea = medium_society add_idea = high_society } }
	...
}
```
（阈值 ±1 触发事件 + 升降级；**idea 阶梯 = 社会等级的展示与生效载体**。）

### 3. 社会展示层：地图模式（`common/map_modes/`）
- `TFR_poverty_mapmode`：按 `higher/high/medium/low/lower_poverty` ideas 逐国着色贫困等级；
- `TFR_disease_mapmode`：按 `global.plague_affected_states` 数组显示疫情州；
- `TFR_culture_map_mode`（10728 行）：文化分布巨型脚本。

### 4. 政党党翼显示（`00_political_parties.txt`）
```pdx
TFR_ruling_party_wings_GUI = {
	window_name = "TFR_ruling_party_wings_GUI_window"
	context_type = player_context
	parent_window_name = ruling_party_wings_bg_anchor     # 国家政治面板党翼锚点
	triggers = {
		ruling_party_wing_indicator_tot_soc_visible = {
			NOT = { has_government = totalitarian_socialist
				check_variable = { political_power_ideology_var = token:totalitarian_socialist } }
			is_in_array = { ROOT.ruling_party_wings_array = token:totalitarian_socialist } }   # 执政党翼指示灯
		# 11 个意识形态各一条（auth_soc/lib_soc/soc_dem/soc_lib/mar_lib/conservative/...
	}
}
party_popularity_number = {  # 顶栏政党支持率数字（parent_window_token = top_bar）
	context_type = player_context
	parent_window_token = top_bar
	window_name = "party_popularity_number_container"
}
```
（党翼 = `ruling_party_wings_array` 数组 + token；政治面板党翼区显示执政联盟成员指示灯。）

## 六、完整数据流

```
① 数据：on_startup 写 GDP/债务/通胀真实数据 + 填 economic_actions_array 4 token
② 结算：on_monthly add_GDP（宏观账本）→ income/debt/gdp 变量更新
         on_monthly update_development（6 项社会发展）→ 阈值检查 → idea 阶梯
③ 显示：顶栏 [Get_GDP_total]/[Get_DEBT]（scripted_loc）
         trade_tab econ_tab_window_gui（类型图标 triggers + 行动 token + 复选框 + 贷款/投资按钮）
         TFR_economy_ledger（6 排序按钮 → 三级聚合 → 全球排名）
④ 交互：玩家点按钮 → effects 直接改变量（add_income/add_debt/add_timed_idea）
         经济行动按钮 → meta_effect 按 token 调 <token>_effect
         复选框 → flag + frame 切换 → add_GDP 中行为改变（自动还债）
⑤ AI：  ai_weights 按 debt_difference 开关自动还款/银行；ai_enabled 内容国
```

## 七、对本项目的借鉴清单

| TFR 机制 | 本 mod 对应需求 | 移植要点 |
|---|---|---|
| 经济行动 token 系统（meta_effect） | 可扩展的"政策/行动"按钮库 | `[TOKEN]_effect/_trigger/_desc` 三件套 + 数组 token——新增零改 GUI |
| 经济类型图标 triggers | 文明/经济制度显示 | 28 种 idea → 各自 visible trigger + 无类型兜底 |
| flag + frame 复选框 | 开关类设置 | frame 1/2 状态 + flag 同步 + 结算逻辑读 flag |
| 贷款/还款按钮 | 借贷机制 | income_var_temp + debt_var_temp 双变量 + 1.5 倍成本 |
| 6 项社会发展变量 | 文明发展度（工业/教育/社会） | 变量 + modifier 累积 + ±1 阈值 + idea 阶梯 |
| 三级聚合账本 | 全球/体系/阵营经济排名 | get_sorted_scored_countries + union 代表累加 |
| AI 参与面板 | 体系决策 AI 化 | ai_enabled + ai_test_interval + ai_weights |

## 附：关键文件路径速查

| 文件 | 作用 |
|---|---|
| `common/scripted_guis/TFR_scripted_guis_ZZZ_economy.txt`（615 行） | 经济标签页 scripted_gui（开关/类型图标/行动/复选框/贷款/投资/AI） |
| `common/scripted_guis/TFR_economy_ledger.txt`（15695 B） | 经济账本 scripted_gui（6 排序按钮 + 指标切换） |
| `common/scripted_guis/00_political_parties.txt`（9585 B） | 顶栏支持率 + 执政党翼指示灯 |
| `interface/TFR_interface_economy.gui`（3784 B） | 顶栏 GDP/债务容器 + GDP 面板 |
| `interface/TFR_economy_ledger.gui`（28984 B） | 经济账本窗口层 |
| `common/scripted_effects/00_TFR_scripted_effects_ZZZ_economic_actions.txt`（4496 B） | 4 个经济行动 effect（印钞/紧缩/战争税/开发州） |
| `common/scripted_triggers/TFR_scripted_triggers_ZZZ_economic_actions.txt` | 行动 trigger + is_economic_action_trigger |
| `common/scripted_effects/00_TFR_scripted_effects_ZZZ_generic.txt`（176KB） | add_GDP 内核 + update_development + check_*/increase_*/decrease_* |
| `common/on_actions/00_TFR_on_actions_ZZZ_money.txt`（40KB） | 开局数据 + 月度 add_GDP + economic_actions_array 填充 |
| `common/on_actions/00_TFR_on_actions_ZZZ_development.txt` | 月度社会发展调度 |
| `common/scripted_effects/TFR_scripted_effects_ZZZ_economy_ledger.txt`（73KB） | 账本计算（三级聚合 + 评分器调用） |
| `common/map_modes/` | 贫困/疾病/文化地图模式 |
