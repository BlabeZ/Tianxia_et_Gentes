# 12-TNO冷战经济与GUI参考（The New Order）

> 适用：**变量模拟型经济系统**、大规模 scripted_gui、1962 式未来开局适配、冷战/超级大国机制、超事件、区域新闻系统。
> 参考样本：The New Order: Last Days of Europe（TNO，`E:\Steam\steamapps\workshop\content\394360\2438003901`，v1.10）。
> **前提**：TNO 是 1962 年开局的三极冷战 mod（`START_DATE = "1962.1.1.1"`、`END_DATE = "1976.12.31.1"`，紧张度全系清零）。其文件规模：497 国家、**2525 州**（原版 1081 的 2.3 倍）、198 国策文件、**133 个 scripted_guis**（远超一切模组）、122 scripted_localisation、198 scripted_effects、283 ideas、TNO_game_rules.txt 595KB（约 577 条规则）。

## 一、总览：TNO 的三个核心差异点

1. **经济 = 巨型变量模拟**：不依赖原版工厂经济，用 ~200 个国家变量 + 176 个 scripted_effects 构建 GDP→生产单位(PU)→预算→通胀→债务→信用评级的完整闭环，月度结算集中在单入口；
2. **机制 = GUI 化**：选举地图、卡牌屋、仪表盘、冷战面板、经济圈、法律菜单全部做成 scripted_gui，游戏机制直接可视化操作；
3. **世界观 = 标签化意识形态 + 冷战数值层**：11 大意识形态 152 子类型全部零修饰（纯标签），真正的玩法差异由"法律系统 + 冷战得分 + 核威慑 + 经济圈"承载。

## 二、经济系统（TNO 最大资产，可整体借鉴）

### 1. 数据层：开局变量定义（`on_actions/ZZZ_economy_definitions.txt`）
```pdx
USA = {
	set_variable = { GDP = 397.644 }          # in billions
	set_variable = { GDP_growth = 6.75 }      # as a percentage
	set_variable = { income_tax_rate = 0.205 }
	set_variable = { poverty_rate = 28.4 }
	set_variable = { national_debt = 313.607 }
	econ_initialize_credit_rating_system = yes
	initiate_display_vars = yes
}
```
200+ 国家逐一设定（JAP 201.458、GER 等）。

### 2. 结算层：月度脉冲单入口（`TNO_on_actions.txt` → `TNO_pulse_effects.txt`）
```
every_country = {
	limit = { econ_can_use_economy_system = yes }
	societal_development_monthly_check = yes
	econ_calculations_ON_MONTHLY = yes
	calculate_consumer_goods_need = yes
}
```
`econ_calculations_ON_MONTHLY`（后端 12950 行）**AI/玩家分叉**：AI 走完整自动链（`econ_calculations_ON_MONTHLY_AI`：投资储备→贫困→贸易整合→经济圈数组→滑块→资金效果→总收入→总支出→赤字/债务→信用评级→央行自动选择（`check_variable = { clamped_inflation_rate > 4.0 }` 选紧缩）→名义 GDP 增长→"橡皮筋通胀"防爆（增长 >10% 触发）→通胀→实际增长→结算→月度增长状态→重算 GDP/PU）。

### 3. 引擎桥接三件套（TNO 经济与引擎的"接线层"）
1. **modifier_definitions**（`TNO_economic_modifiers_definition.txt` 491 行）注册 40+ 经济键：`annual_gdp_growth_factor`、`production_units_to_GDP_ratio_modifier`、`debt_to_GDP_ceiling_modifier`、`inflation_rate_modifier`、`interest_rate_modifier`、`misc_costs_percent_of_GDP_modifier`、`state_GDP_contribution_to_total_state_GDP_modifier`、`state_resource_power`（电力）等；
2. **dynamic_modifiers**（`TNO_misc_econ_effects.txt`）把变量映射进原版 modifier 槽：
```pdx
credit_rating_dynmod = { stability_factor = stability_from_credit_rating }
tax_hike_dynmod = { sales_tax_rate_modifier = tax_hike_value_sales ... }
KD_Large_Hydro_Electrical_Plant = { state_resource_power = 5 state_GDP_growth_modifier = 0.5 }
```
3. **offsite buildings**：PU 分配为三类（`PU_civilian_factories`/`PU_military_factories`/`PU_consumer_goods`）后 `add_offsite_building = { type = industrial_complex level = X }` 转化为原版工厂条数字——玩家看到的工厂数由 PU 驱动。

### 4. GDP 自底向上（州价值）
每个州有 `state_value` 变量；国家 GDP = 各州 `state_GDP_contribution` 之和（`every_owned_state` 遍历累加，除以 1000 转 B 单位）；占领按 `state_GDP_kept_on_occupation_modifier` 削减；征服战争在和平处理中 -15% GDP（KD's Consequences of War）。

### 5. 经济圈与信贷阶梯
- 经济圈：`ECON_SPHERE_LEADER` 变量指向圈主（20+ 圈），`econ_recompile_all_spheres` 每月重建成员数组、汇总圈内 GDP、算 `econ_sphere_world_percent`（直接计入冷战外交分），地图模式按圈主染色；
- 信贷阶梯：1-10 级 + 0-100 进度条，`apply_credit_rating_effects` 按等级写利率/债务上限/稳定度效果。

### 6. 经济 GUI（`TNO_economy.txt` 4362 行）
文件头注释即目录（Econ Base/Macro/Social/Trade/Construction/Production 六大子菜单）；GDP 州显示 `gdp_state_display`（`dirty = state_value`）、电力开关（`TNO_lights` 变量）、顶部栏经济。所有改动 `add_to_variable = { TNO_economy_GUI_dirty = 1 }` 触发重绘。

### 7. 经济 ideas
`TNO_zz_Econ_Types.txt`：三大经济类型（Econ_Type_Capitalism/Corporatism/Planned）+ 18 亚型；`TNO_zz_social_development.txt`：研究设施六级（makeshift→cutting_edge，各带 `research_facilities_monthly_rate` 拨款）。

**启示**：《天下与万邦》的"多中心资本主义/朝贡经济/财政危机"若要深度模拟，TNO 是唯一范本——但工作量大（176 effects + 15000 行），建议**初期只做简化版**（GDP 变量 + 财政收支 + 朝贡贸易额三件套）。

## 三、GUI 系统（133 个 scripted_guis 的设计模式）

### 1. 窗口三层结构
`XXX_Open`（挂在原版窗口 token 上的开关按钮）→ `XXX_Main`（`parent_window_token = "XXX_Open"` 主窗口，国家 flag 控制显隐）→ 多个子窗口（parent_window_token 链式挂载）。挂载点复用：`politics_tab`、`trade_tab`、`top_bar`、`selected_state_view`、`powerbalanceview`、`decision_category`。

### 2. 四层咬合（TNO GUI 核心）
- **数据层**：遍布全球/国家的变量数组（`USA_states_icon_array^idx`、`BOR_SIGType`、`ElectionSeason_ActiveStates`、`TNO_BoP_Tabs`）；
- **展示层**：properties 用 `frame = 变量^索引`（数组/年份作索引的帧动画）、`image = "[GetXXX]"`（scripted_loc 动态贴图）、`x/y = 变量数组`（50 州坐标数组）；
- **逻辑层**：effects/triggers 内嵌 GUI（按钮点击直接操作数组/变量/调用 scripted_effects）；
- **文本层**：122 个 scripted_localisation 的 defined_text（`GetSenator_1` 按变量查表、`GetSubIdeologyLoc` 分级查表、`Get_fopo_tab_name` 按冲突 token 动态标题）。

### 3. dynamic_lists（数组→界面条目）
```pdx
dynamic_lists = {
	TNO_Politics_Law_Grid = {
		array = TNO_Politics_Law_display
		change_scope = no
		entry_container = "TNO_pol_category_[?TNO_Politics_Law_display^i]"
	}
}
```
可 `change_scope = yes` 切到州作用域（英格兰选举季用 state 数组逐州生成选举框）。

### 4. 法律系统 GUI（`TNO_Politics.txt`）
原版 6 个法律槽扩展为 **6 大分类 × 40+ 部法律**（政党制度/宗教/工会/移民/奴隶制/新闻/投票权/征兵/贸易/税/福利/教育/性别等），每部 3-8 档。法律档位用 **token 数组**表达（`add_to_array = { tno_laws_display_selection = token:tno_vote_franchise_universal }`），法律名用 `GFX_idea_[?law_v.GetTokenKey]` 动态拼接贴图；每条法律配 0-100 的 `tno_xxx_effectiveness` 变量（政策有效性）。

### 5. AI 也能操作 GUI（进阶特性）
```pdx
ai_enabled = { original_tag = GER }
ai_check = { check_variable = { WWSControl > 0 } }
ai_test_interval = 168
ai_weights = {
	ger_economy_menu_open_click = { ai_will_do = { base = -1 modifier = { NOT = { has_country_flag = GER_Economy_GUI_open_flag } add = 10 } } weight = 1 }
}
```

## 四、意识形态：标签化（11 大 × 152 子类型）

`common/ideologies/00_ideologies.txt`（505 行）：11 大意识形态（national_socialism/fascism/ultranationalism/despotism/paternalism/conservatism/liberal_conservatism/liberalism/progressivism/socialist/communist）× 子类型（最多 27 个）+ 每大意识形态 `_1~_4` 编号渐变变体。**全部零修饰**：无 rules/modifiers/faction_modifiers、`dynamic_faction_names = {}`、`can_be_boosted = no`、`ai_neutral = yes`（文件头注释：所有意识形态并入 3 个 AI 组，最后全用中性 AI——因为开局紧张度极低原版分阵营 AI 不互动）。

子类型 = 政治路线标签（美国 dynastic_liberalism_kennedy/lbj/hart 六家族变体、汪伪思想、蒋氏思想、勃艮第体系、buddhist_socialism 等）。**政体判型靠 scripted_triggers**（`has_elected_government`/`has_authoritarian_government`/`has_dictatorship_government` 聚合 11 意识形态）。

## 五、科技：1962 开局的"分级门控"（不重排原版树）

**关键结论**：TNO 保留原版全部 1936-1945 科技及命名，不删除不重命名；在每个科技上挂 `allow` 条件，用**经济系统（研究设施 idea 等级）**决定谁能研究哪一代：
```pdx
fighter_1960 = {
	allow = { AND = { TNO_KD_Can_Research_Modern_Tech = yes TNO_KD_Can_Research_Modern_Manufactoring = yes } }
	enable_equipments = { jet_fighter_equipment_2 }
	start_year = 1960
}
```
- 门控触发器链（`TNO_econ_triggers.txt`）：`TNO_KD_Can_Research_Basic_Tech`（≤1945）→ Outdated（1950）→ Modern（1960-70）→ Advanced（1980），基于 `tno_research_facilities_*` idea 等级，**1969.12.30 后自动降级解锁**（科技代际扩散）；
- 代际序列：1936 → 1945 → 1950 → 1960 → 1970 → 1980 → **1990**；步兵新增 `infantry_kit_*` 系列（真实装备年份命名：kit_4 = 1958 年式）；
- WMD 科技隐藏（`hidden_folder`）+ `ai_will_do = { factor = 0 }`，只由历史/事件获得（`nuclear_weapons = { allow = { always = no } }`）；
- 开局：超级大国满配 1960 科技 + ICBM/MRBM/SRBM/核武（德国 `set_technology` 中直接 `ICBM = 1 nuclear_weapons = 1`）；第三世界只能摸 1945 旧货——**科技鸿沟即冷战鸿沟**。

## 六、学说：大战略学说重写 + 经济联动

4 条陆战大战略学说替换原版：maneuver_warfare（机动）/ strategic_warfare（战略）/ defensive_warfare（防御）/ unconventional_warfare（非常规，XP 50）；**milestones 奖励经济变量**（`research_facilities_monthly_rate = 2`、`army_professionalism_monthly_rate`，写入 milestone_var 供其他系统读取）；AI 选择按 **tag 白名单强控**（机动战只许 GER/OMS/WRS/CLC/SPH/GOR 等 6 tag）。

装备：MBT/IFV/APC 取代原版坦克序列（`combat_width = 2`、`need = { MBT_chassis = 40 }`）、4 代直升机、导弹（自杀机）、Kugelpanzer 球形坦克（meme，归入 IFV 类）。AI：ai_strategy_plans **几乎弃用**（1 个文件，仅游戏规则-国策权重分流），真正控制 AI 的是 default.txt 工厂分配/师上限（`TNO_DIVISIONS_CAPPED` flag + PU 限员）+ 地区驻军策略。

## 七、独特国家机制

| 国家/机制 | 实现 | 参考文件 |
|---|---|---|
| 德国四法理政权（GCW） | BGR/GGR/HGR/SGR 四 tag；`GER_GCW_select_victor` **计分制**（兵力/装备/投降进度各 1 分 + 元首遗嘱 flag 加权 2 分）判胜负 | `TNO_GER_Germany_GCW_scripted_effects.txt` |
| 施佩尔改革 | `SGR_Alignment` 五档（-5/-2/0/2/5）驱动 Speerdometer 仪表盘 GUI；国策/决策累计社会倾向，CIA 可干预 | `TNO_GER_Speer_StateReich_scripted_effects.txt` |
| 鲍曼卡牌屋 | 三大派系 × **12 个 SIG**（党务官僚/人民/教会/陆军/海军/中央工业/莱茵工业/奴隶种植园/银行…），各带 Power + 对三派系 Loyalty 数组；`BOR_Control_Update` 算"可控百分比 = 可控派系力量之和/总力量" | `TNO_GER_Bormann_Kartenhaus_scripted_effects.txt` |
| 海德里希/勃艮第 | 地堡/核武进度变量（Progress/Quality/Time_Remaining）；勃艮第**月度脉冲** + "警察对工人比率"监视（`BRG_Cop_To_Worker_Ratio`，不足打 flag 地图标红） | `TNO_GER_Heydrich_*`、`TNO_Burgundy_*` |
| 美国选举 | **7 群体 × 6 政党 affiliation 变量矩阵**（black/hispanic/minority/nativist/urban/rural/union × com/pro/dem/anv/nat/rep），每周 tick 转移；国会法案：每法案定义各党支持率 + `flip_cost` 拉票成本 | `TNO_USA_election_effects.txt`（19270 行）、`TNO_USA_bill_setup.txt` |
| 俄罗斯统一（Smuta） | 三阶段 flag（warlord→regional→superregional）；`RUS_Smuta_Enable` 设 Chaos/Supplies/CoringCost 变量；六级统一决策（total/siberian/west_russia 等） | `TNO_RUS_Smuta_scripted_effects.txt` |
| 日本 | `JAP_monthly_pulse`：Diet 议会 + 派阀满意度 + 总理 flag 互斥；派阀席位用数组模拟 | `TNO_JAP_scripted_effects.txt` |
| 广东 | **8 棵 focus_tree 按剧情阶段切换**（suzuki→yasuda_crisis→silicon_years→oil_crisis→riots→ending）；状态变量切换 11 个 dummy idea | `TNO_Guangdong_*` |
| 伊比利亚 | 稳定度变量映射六级国家精神；14 个 TAG 一次性打 `is_iberian_nation` flag | `TNO_IBR_scripted_effects.txt` |

**国策树"空心化"设计**：`focus_tree` 壳（条件装载）→ `shared_focus` 实体（UI 定位 + tooltip）→ 实际逻辑全在 `completion_reward` 背后（GUI 按钮/事件/决策）；`allow_branch` 限定元首（只有希特勒在位才能进入开局树）；德国开局树只有 1 个 focus（登月序章 "fakeout"），完成后事件切换到真正四政权树。

## 八、冷战机制（三极数值层）

- **超级大国**：`set_superpower`（`TNO_Cold_War_scripted_effects.txt`）加入 `global.TNO_Superpowers` 数组 + 挂得分/投射修正；三方紧张度变量 → `superpower_ger_usa_tension_modifier` 动态修正（战争支持/稳定/工厂产出/核生产按变量缩放）；
- **核武库**：开局库存 GER 12382/USA 20102/JAP 8147，`nuclear_stockpile_min_cap = 750`；`calculate_strike_capability` =（发射井×1000 + 潜艇×10 + 战略轰炸机×3）/库存，clamp 0-1；`nuclear_global_coverage` 全球覆盖百分比；
- **7 海战区**：`CW_SeaZone_Status^0..6` 数组（1=控制），力量投射 = 每控制一区 +2.5% PP（`Cold_War_GUI_PowerProjection_CalculateBonuses`）；
- **世界紧张度**：`global.TNO_World_Tension`（0-100）独立变量，年度衰减，海德里希线/WW3 强制 100；
- **冷战得分**：军事分（职业化档位 + 核武库×打击能力）+ 经济分（人均 GDP/债务/贫困/科技）+ 外交分（含经济圈占世界 GDP 比）；超级大国效果经 `score_effects_array` 注入 6 项修正。

## 九、世界事件与超事件

- **区域兴趣过滤**：`on_startup` 按 `HasEuropeInterest/HasAsiaInterest/...` 设 6 个兴趣旗标，`TNO_WorldEvent_reorg_on_actions.txt` + 区域新闻订阅 GUI（玩家可勾选订阅哪些大陆新闻）；
- **世界事件库**：`events/TNO_WorldEvents.txt`（**17502 行**，WORLD.xxx 全模组引用 1131 处），事件号段分区管理（WORLD.700-999 美意、WORLD.18xxx 非洲、WORLD.30xxx 中东）；
- **超事件**（`TNO_super_events_scripted_effect.txt` 132 行）：`TNO_fire_super_event` 用 **token 变量**（`TNO_super_event = TNO_temp_super_event` + 128 个 `SE_*` 同步 token）管理；核战爆发（`TNO_my_world_is_on_fire_how_about_yours` 全局旗）后不再触发新超事件；游戏规则三档（默认/无音频/禁用），**禁用时自动执行超事件选项效果**（保证剧情连续性）；与俄罗斯统一结局系统深度耦合。

## 十、地图与州

- **2525 州**（原版 1081 的 2.3 倍），州文件带**自定义建筑**（offices 办公楼/barracks 兵营/hospitals 医院/thermoelectric_plant 发电厂/schools/prisons/nuclear_reactor/missile_silo/enrichment_plant 浓缩厂）+ `GDP_category_*` 州旗标（GDP 初始分类）+ `universal_renamings` 动态改名旗标；
- **continent.txt 14 大陆**：在原版 7 大陆上拆出 `eastern_europe`、`middle_east`、`antarctica`、`pakistan`、`gangetic_plain`、`india`——支撑区域利益新闻与事件过滤；
- **7 个脚本地图模式**：GDP 人均着色（按 state_GDPPC 分段插值）、经济圈染色、经济类型、文化分布（10728 行巨型脚本）、行政头衔、建筑。

## 十一、对本项目的借鉴清单

| TNO 机制 | 本 mod 对应需求 | 移植要点 |
|---|---|---|
| 变量模拟经济（GDP→PU→预算→评级） | 大顺财政/多中心资本主义 | 简化版三件套（GDP 变量 + 收支 + 朝贡贸易额）；modifier_definitions → dynamic_modifiers → offsite buildings 接线层照抄 |
| 133 个 scripted_gui | 天下体系面板/廷议/改革界面 | 四层咬合模式（数组数据层 + frame/image 展示层 + 内嵌逻辑 + defined_text 文本层） |
| 科技分级门控 | 1910 开局的科技代际 | `allow = { TNO_KD_Can_Research_* }` 式门控触发器 + 研究设施 idea 等级 + 时间自动扩散——比重排科技树省力得多 |
| 法律系统 GUI（6 类 40+ 法） | 大顺法律/制度体系 | token 数组档位 + `tno_xxx_effectiveness` 政策有效性变量 |
| 标签化意识形态 | 8 大意识形态做"文明现代性标签" | 11 大×152 子类型零修饰模式 + `has_elected_government` 聚合触发器 |
| 超事件 token 管理 | 天下大战/开幕 | token 变量 + 同步 token 表 + 游戏规则三档 + 禁用自动执行 |
| 区域兴趣新闻 | 各文明圈新闻播报 | 兴趣旗标 + 订阅 GUI + 事件号段分区 |
| 冷战数值层 | 天下-威斯特伐利亚-伊斯兰三体系竞争 | 超级大国数组 + 体系紧张度变量 + 得分排名（可做"天下秩序得分"） |
| 核威慑 | （如需） | 库存 + 打击能力公式 + 覆盖百分比 |
| 14 大陆划分 | 天下圈/欧洲圈/伊斯兰圈地理判定 | continent.txt 扩展 + 区域兴趣过滤 |
