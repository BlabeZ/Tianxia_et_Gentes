# 13-TFR现代战争与宏观账本参考（The Fire Rises）

> 适用：现代世界观开局（2020 式）、宏观账本经济（TNO 的简化取舍版）、国际组织自建系统、大型内战（多实体分裂）、巨型分支和平系统、现实事件排程。
> 参考样本：The Fire Rises（TFR，`E:\Steam\steamapps\workshop\content\394360\3350890356`，v1.2025.0b）。
> **前提**：TFR 是 2020 年开局的现代战争 mod（`START_DATE = "2020.1.1.1"`、`END_DATE = "2050.1.1.1"`，全接管式 replace_path 100+ 条）。规模：612 国家、1493 州、723 国家定义、60 国策文件、145+ 游戏规则、scripted_effects 38（SOV 单文件 23400 行）、16 个 BOP。

## 一、总览：TFR 的四个核心特征

1. **现实模拟 = 事件排程**：on_startup 用 `days = N` 精确复刻 2020-2025 现实事件（COVID 疫情链、美国 2020 大选 313 天倒计时、纳瓦利内中毒、沙特王位更替、恒大债务危机、台海局势）；
2. **经济 = 宏观账本**（TNO 全模拟的"简化取舍版"）：月度 `add_GDP` 结算 + **现实数据锚定**（美国 23.7 万亿债务）+ 修正因子注入；
3. **国际组织 = 自建系统**：NATO/EU/BRICS/CSTO/PEC 不用原版阵营，用 idea + dynamic_modifier + 数组旗标 + scripted_gui 自建；
4. **内战 = 多实体分裂**：美国二次内战分裂成 14+ 实体（预置国家 + transfer_state + 合法性变量），全球多国内战由 145+ 游戏规则预设结局。

## 二、经济系统：宏观账本（TNO 的取舍版）

### 1. add_GDP 月度结算（`00_TFR_scripted_effects_ZZZ_generic.txt` 1132 行起）
```pdx
add_GDP = {
	# 收入端
	every_controlled_state = { add_to_variable = { var = ROOT.office_park_total_var value = building_level@office_park } }
	set_variable = { var = business_value_var value = num_of_civilian_factories }
	multiply_variable = { var = business_value_var value = modifier@business_value }   # 商业价值
	set_variable = { var = personal_value_var value = max_manpower }
	multiply_variable = { var = personal_value_var value = 0.00001 }                    # 个人所得税
	set_variable = { oil_export = resource_exported@oil }
	multiply_variable = { var = oil_export value = 0.1 }                                # 出口收入
	# 支出端：军费（步兵营 0.01/营 → 航母 1.0/艘）+ 债务本息（debt_var/12 × interest_rate）
	# 净变化 → 自动还债或累积收入；通胀月度累积；年化 GDP = 月度 × 12；实际 GDP 用 1+通胀折算
}
```
- **现实数据锚定**：on_startup 写入真实债务/通胀（USA 23719.2 亿、PRC 8662、JAP 10640）；
- **GDP 校正库**（`00_TFR_ideas_ZZZ_economic_hidden.txt`）：各国专属 `gdp_fix` hidden idea（如 `SOV_gdp_fix`：income_growth -4.25% 等）让模拟 GDP 贴近 2020 现实；
- **动态修正传导**（`TFR_dynamic_modifiers_ZZZ_economic.txt`）：`gdp_debt_dynamic`（债务/GDP 超阈值按比例惩罚科研/工业/稳定）与 `inflation_dynamic`（通胀影响消费品/效率/稳定）——所有数值经 `debt_dynamic_var` 等变量注入；
- **经济行动**（`00_TFR_scripted_effects_ZZZ_economic_actions.txt`）：印钞（+50% 收入 +50% 通胀，175 天限时 idea）/量化紧缩/战争税（税率 +25%、稳定 -10%）/开发州（state_category 升级链 wasteland→megalopolis，逐级扣钱）；
- **经济账本 GUI**（`TFR_economy_ledger.txt` + scorers）：`get_sorted_scored_countries` 用评分器（GDP/实际 GDP/债务/工厂/资源）排序全球 + 国际组织/阵营/全球三级聚合——**全球排名展示**。

### 2. 与 TNO 对比（本项目决策参考）
| | TNO（全模拟） | TFR（宏观账本） |
|---|---|---|
| 结算 | 每 10 天全模拟经济循环 | 月度一次 add_GDP |
| GDP 来源 | 工业+资源+服务业分项 | 民厂×商业价值 + 人力×个人价值 + 出口 + 杂项 |
| 数据 | 模拟推导 | **现实锚定**（真实债务/通胀）+ gdp_fix 校正 |
| 玩家交互 | 精细面板 | 4 个经济行动 + 税率法 |
| 复杂度 | 176 effects / 15000 行 | ~1000 行 |

**本项目建议**：TFR 式宏观账本更适合《天下与万邦》初期——1910 世界 GDP/财政/朝贡收支用"现实锚定 + 月度结算 + 修正因子"即可表达，避免 TNO 式巨型模拟的工作量。

## 三、国际组织自建系统（NATO/EU/BRICS/CSTO/PEC）

**关键结论**：现代组织**不用原版 faction 系统**（模板全部 `visible = { always = no }` 停用），用四件套自建：

1. **成员数组 + idea**：`USA_add_to_nato` 把国家加入 `USA.USA_nato_members` 数组；成员挂 `NATO_unity_2` 等 idea；
2. **联盟级变量广播**（EU 模式）：`EU_join_effect` 把 ~50 个 `global.eu_*_dynamic_var` 复制到成员国本地变量 → `EU_member_dynamic` 动态修正读取——**联盟加成中心化定义、成员本地生效**；`EU_leave_effect` 清变量；法西斯欧洲变体（大陆封锁体系）、欧元 idea（+10% 工厂 +20% 收入增长）；
3. **领导权争夺**：`GER/FRA/ENG_add_nato_leadership`（0-1 变量）→ `NATO_who_won_the_election` 比较三变量定 `set_global_flag = GER_won_leadership_global`；
4. **联盟级军力聚合 GUI**（`TFR_nato_gui.txt`）：点击后聚合全阵营**总兵力/工业/军队构成/资源**（`every_country` 遍历 + `every_owned_state` 建筑统计）写入 `global.nato_*` 变量显示——"联盟级军事经济总览"。

国际组织地图模式（`TFR_map_modes.txt`）：按 `EU_member_dynamic`/`arab_league_member`/`SOV_brics_dynamic` 等修正/idea 逐一染色（欧盟蓝/阿盟绿/ADS 红/金砖绿）。科技共享组配套：`nato_research`（绑 GER 阵营）/`csto_research`（绑 SOV）/`eadi_research`（绑 PRC）/`pdto_research`（环太平洋防御条约）。

**本项目适用**：天下体系/威斯特伐利亚/伊斯兰体系的"联盟加成"完全可用此模式（成员数组 + 联盟变量广播 + 地图染色 + 军力总览）。

## 四、意识形态：11 大 × 190 子类型（现实命名）

`common/ideologies/TFR_ideologies.txt`（1472 行）：11 大意识形态（totalitarian_socialist/communist/libertarian_socialist/social_democrat/social_liberal/market_liberal/conservative/authoritarian_democrat/nationalist/fascist/national_socialist），每大 6-30 子类型（共约 190）。

- **子类型大量以现实人物/思潮命名**：putinism、kadyrovite_tendency、trumpism_conservative/market/authdem、xi_jinping_thought、lukashenkoism、zhirinovsky_thought、falun_dafa、jucheism、transhumanism、econazism 等，全部 `can_be_randomly_selected = no` 锁定；
- **modifiers 全空、rules 全部一致**（`can_puppet = no`、`can_join_factions = no`、`can_access_market = no`、`can_force_government = no`）——意识形态纯标签，外交/经济由自建阵营与制裁系统承担；`can_access_market = no` 配合自建共同市场机制；
- 保留 `national_socialist` 为独立大组（含 eurasianism、identitarianism、accelerationist 等现代极右亚文化）；
- 显示系统：`TFR_subideology_scripted_loc.txt`（60KB）`GetIdeologySubtype` 按政府类型分发到 11 个查表。

## 五、美国二次内战（TFR 核心玩法）

### 1. 触发链：BOP → 大选 → 军队断通讯 → 分裂
- **信任度 BOP**（`TFR_bop_USA.txt`）：`USA_trust_bop`（拜登侧 vs 特朗普侧，7 档），玩家国策站队（`USA_side_with_trump` 拉向一侧）；每进一档触发大选结果事件（`random_list` 权重特朗普/拜登），档位越高惩罚越重（-50 至 -250 PP）+ 内战任务倒计时缩短；
- 大选结果（`usa.128` Trump Wins / `usa.14` Biden Wins）→ `usa.5`（**Army Stops Communications** 军队切断通讯）→ `USA_civil_war_outbreak_effect`。

### 2. 分裂实现：预置国家 + transfer_state（约 60 州）
```pdx
USA_civil_war_outbreak_effect = {
	USB = { USA_civil_war_faction = yes
		set_variable = { var = USB_influence_pro_var value = 0.35 }   # 三派影响力
		transfer_state = 1122  transfer_state = 361 ...               # 约 40 州
		every_state = { limit = { NOT = { is_core_of = USB } OR = { is_controlled_by = USB ... } } add_core_of = USB }
		every_controlled_state = { limit = { is_core_of = USB } create_unit = { division = "Volunteer Militia" ... } }
		USA = { set_nationality = { target_country = USB character = USA_ben_hodges_char } ... }  # 17 名将领转国籍
	}
	LOU = { USA_civil_war_faction = yes transfer_state = 978 ... new_country = yes }
	...
}
```
碎片实体：USB（东北+西海岸联盟）/USC（南方）/APA（人民解放军）/NSM（国家社会主义运动）/LOS/PTF/ATW/CAC（卡斯卡迪亚）/GMA/LOU/MSS/LWK/RRR/IKA/ALA/NCA/STC/GRA 等 14+ 实体 + 帮派（HLA/LCN/MS13/ZET/CDJ）+ 民兵（ATH/ATP/CHZ）。

### 3. 合法性核心资源（`USA_civil_war_faction`）
```pdx
set_variable = { var = legit_var value = 0 }        # 合法性 0-100
set_variable = { var = recore_pp_var value = 50 }   # 重夺核心成本
set_variable = { var = recruit_pp_var value = 25 }
add_dynamic_modifier = { modifier = USA_legitimacy_dynamic }
```
内战玩法 = 合法性争夺（夺城/国策/游说决策增减）→ 胜利方 `annex_core_faction = yes` + 按胜利方给自治修正（`CAC_northwest_autonomy_dynamic` 等）；重夺核心决策消费 recore_pp_var 逐步核心化。

### 4. 开战矩阵（`USA_civil_war_begins`）
西海岸帮派互宣 `civil_war` 型战争、墨西哥边境帮派用 `annex_everything` 互吞、`930 = { add_dynamic_modifier = { modifier = USA_lawless_city_state_dynamic } }` 无政府城市；`on_state_control_changed` 逐城结算全球内战事件（Boston/Philadelphia/Sacramento 等，全局 flag 防重）。

## 六、现实事件排程（2020 沉浸感根基）

`00_TFR_on_actions_ZZZ_startup.txt`（1812 行）四层初始化：
1. **政体系统**：17 种政体理念（`ZZZ_*_political_system`/`republic`/`monarchy`/`dictatorship`/`theocracy`），GUI 映射政体图标；
2. **政党支持率与联盟**：每国计算 party_popularity + 预设执政联盟/党翼（美国开局党翼 = authoritarian_democrat）；
3. **经济类型**：9 种（美国资本主义/计划经济/社会主义市场经济/寡头资本主义等，`change_economy_type_*`）；
4. **制裁与世界局势**：`send_embargo` 连锁制裁（SOV/PER/PRK/VEN/TAL/HRL/SYR/PAL/HEZ/SHB）+ `country_event = { id = xxx days = N }` 精确排程：
   - 美国：`usa.203` **313 天（2020.11.3 大选日）**；
   - 中国：`china.10` 9 天首次 COVID、`china.318` 1322 天恒大债务危机、`china.373` 1855 天《哪吒2》、`china.124` 1460 天香港国安法；
   - 俄罗斯：`russia.1` 245 天纳瓦利内中毒、`russia.20` 690 天普京新冠；
   - 沙特：`saudi.12` 68 天石油协议失败 → 156 天萨勒曼驾崩 → 180 天穆罕默德加冕。

## 七、巨型分支和平系统（TNO 黑魔法）

`TFR_on_actions_ZZZ_peace.txt`（**27386 行**）`on_capitulation` 完全接管原版投降（注释 "go away stinky vanilla peace"）：
```pdx
on_capitulation = {
	effect = {
		FROM = { save_global_event_target_as = winning_country }
		ROOT = { save_global_event_target_as = losing_country }
		if = {   # 每个战争配对 = 一个 if 分支
			limit = { FROM = { original_tag = FAF } ROOT = { original_tag = CYP } }
			ROOT = { white_peace = GER; white_peace = FAF; white_peace = ENG
				FSY = { annex_country = { target = ROOT } }
				FAF = { puppet = FSY }
				FSY = { set_politics = { ruling_party = nationalist ... } } }
			set_global_flag = skip_default_capitulation
		}
		...
		set_global_flag = war_continuing   # 未匹配的战争继续打
	}
}
```
规则：胜负方配对分支（white_peace + annex/puppet/改组政权/事件）→ `skip_default_capitulation` 跳过原版；不匹配的战争设 `war_continuing` 继续。和平弹窗（`TFR_peace_popup_window` GUI）显示胜败国旗。**这是《天下与万邦》做"体系间战争定制和约"的直接范本（可精简）**。

## 八、现代军事（科技时间轴前移）

- **科技**：保留原版全部科技 ID，`start_year` 整体前移（`gwtank_chassis` 1980、`main_battle_tank1` 1980、科技树从 2000 起算）；代际：战斗机 fighter1(2000)→fighter2(2020 开局标配)→fighter6(2036)、步兵武器 weapons1(2000)→weapons6(2036)；无现实型号命名（F-35 只出现在装备图/命名，科技 ID 用代际编号）；自杀无人机链（俄伊特供，制导导弹装备化）、网络战/量子计算链、`tech_cyber_units_warfare`（hidden，仅 effect 授予）；
- **学说**：三极地缘学说——`nato_western_doctrine`/`csto_eastern_doctrine`/`assymetric_warfare`（非对称，XP 仅 15，武装团体用）；subdoctrine 含无人机蜂群（drone_swarm）、未来士兵（future_soldier，XP 150，需 2030s 外骨骼科技）；
- **装备兵种**：MBT 现代坦克链（8 代）、制导/弹道/核/SAM 导弹、自杀无人机大队、外骨骼支援连（`exoskeleton_support`，步兵软攻 +0.1）、`derzhavnik_battalion`（俄罗斯"国家力量"营）、`bus`（移动指挥部）、共军高达（`#共军有高达` 彩蛋）；
- **AI**：ai_strategy_plans 69 个文件**绝大多数 0 字节占位**（刻意覆盖禁用原版计划！），仅 NATO/PRC 2 个有内容——剧本化 AI 靠 ai_strategy 时间窗（`SOV_boost_economy_strategy` 2024 前 / `SOV_build_for_war_strategy` 2024-2028 / 军备竞赛 2028-2032）+ 游戏规则驱动；
- **战争目标**：普通宣战成本高（200+50/省、限 5 省）抑制 AI 扩张；吞并/颠覆/内战类 `always = no` 只由事件授予——**战争完全剧本驱动**。

## 九、其他独特机制

- **战争升级 10 级**（`war_escalation_scripted_gui.txt`）：`GER_war_escalation_level` 变量 + 决策升级 + 颜色差异化（对 SOV 红/对德法绿，scripted_loc 判定）；
- **超事件**（`TFR_super_events.txt` 1630 行）：每个超事件 = 一个 scripted_gui 窗口（国家/全局旗标触发 + `super_events_off_flag` 全局开关）——比 TNO 更简单直接的实现；
- **核沉降**：`on_nuke_drop` 给目标挂 `fallout_atomic` 修正 730 天（2 年核沉降）；
- **占领城市新闻流**：`on_state_control_changed` 6500 行，SOV-NATO 战争期间每占一个关键城市触发新闻事件（一次性全局 flag）；
- **北约 AI 削弱**：开局给小国挂 `NATO_anti_militarists_idea`（动员 -40%），注释明说防北约 AI 暴兵碾压俄罗斯 AI；
- **COVID 系统**：口罩产量变量（`mask_daily_gain_var`）、州级爆发任务、疫苗研发任务、疫情 idea 阶梯（FRA_covid_idea_1..5）；
- **发展系统**：6 项社会发展（工业/贫困/农业/学术/军事/社会）阶梯式升降（±1 阈值触发事件），州类别升级链 13 级（含 suburb/conurbation）。

## 十、对本项目的借鉴清单

| TFR 机制 | 本 mod 对应需求 | 移植要点 |
|---|---|---|
| 宏观账本经济 | 大顺财政/朝贡收支 | add_GDP 月度结算 + 现实锚定 + gdp_fix 校正 + 账本 GUI 排名 |
| 国际组织自建 | 天下体系/威斯特伐利亚/伊斯兰体系 | 成员数组 + 联盟变量广播 + 领导权争夺 + 军力聚合 GUI + 地图染色 |
| 多实体分裂内战 | 大顺崩解/北美五极/体系战争 | 预置国家 + transfer_state + new_country + 将领转国籍 + 合法性变量 |
| 巨型分支和平 | 体系间定制和约 | on_capitulation 分支表（精简版） |
| 现实事件排程 | 1910-1915 世界事件 | days = N 精确排程 + 全局 flag |
| 科技时间轴前移 | 1910 开局科技 | 保留原版 ID + start_year 前移（与 TNO 门控法二选一） |
| 三极地缘学说 | 各文明军事学说 | 阵营绑定学说 + 非对称低 XP 学说 |
| 战争剧本驱动 | 天下大战触发 | wargoal always=no + 事件授予 + 巨型分支和平 |
| 超事件 GUI 库 | 重大事件播报 | 旗标触发 + 全局开关（比 TNO token 法简单） |
| 战争升级条 | 体系冲突升级 | 变量 + 决策 + 差异化颜色 |
| 现实命名子意识形态 | 各文明政治路线 | putinism/trumpism 式命名 + can_be_randomly_selected = no |
