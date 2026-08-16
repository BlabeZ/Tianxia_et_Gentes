# Token vocabulary — what to put inside raw-script fields

A **curated, high-signal** list of the tokens you'll reach for most when filling raw-script fields
(`completion_reward`, `effects`, `available`, `modifier`, …). This is a **filling aid, not the
authority** — POST your tokens and let `export/validate` + `lint/tree-validation` tell you what's wrong;
your game's `error.log` is the final gate. For a token not listed here, write it and validate.

Which field takes which category is in `_raw-script-fields.md`.

---

## Effects (go in effect fields — `completion_reward`, `immediate`, option `effects`, `complete_effect`, …)

**Politics / economy**
- `add_political_power = N` · `add_stability = 0.05` · `add_war_support = 0.05`
- `add_ideas = <idea_id>` · `remove_ideas = <idea_id>` · `swap_ideas = { remove_idea = a add_idea = b }`
- `set_politics = { ruling_party = <group> elections_allowed = yes }`
- `set_party_name = { ideology = <group> name = <loc_key> long_name = <loc_key> }`
- `add_popularity = { ideology = <group> popularity = 0.1 }`

**Country / diplomacy**
- `add_to_faction = <TAG>` · `create_faction = "<loc>"` · `set_rule = { … }`
- `declare_war_on = { target = <TAG> type = annex_everything }` · `white_peace = <TAG>`
- `puppet = <TAG>` · `set_autonomy = { target = <SUBJECT> autonomy_state = autonomy_dominion }`
  (run in the OVERLORD's scope, `target =` the subject — direction matters)
- `transfer_state = <state_id>` · `add_state_core = <state_id>` · `set_state_owner = <TAG>`

**Focus / research / equipment**
- `add_tech_bonus = { bonus = 0.5 uses = 1 category = <cat> }` (cats: `infantry_weapons` `artillery`
  `land_doctrine` `industry` `electronics` `naval_doctrine` `air_doctrine` … — `construction`/
  `infrastructure` are NOT categories, use `industry`)
- `set_technology = { <tech> = 1 }` · `add_equipment_to_stockpile = { type = <eq> amount = N }`
- `unlock_decision_category_tooltip = <cat>` · `load_focus_tree = <tree_id>`

**Characters / leaders**
- `promote_character = { ideology = <subtype> }` · `promote_character = <char_token>`
- `create_country_leader = { … }` · `kill_country_leader = yes` · `set_character_name = <token>`
- `add_country_leader_trait = <trait>` · `recruit_character = <char_token>` (history only)

**Variables / flags / tooltips**
- `set_country_flag = <flag>` · `clr_country_flag = <flag>` · `set_global_flag = <flag>`
- `set_variable = { var = X value = 5 }` · `add_to_variable = { var = X value = 1 }`
- `custom_effect_tooltip = <loc_key>` (needed for variable/flag effects — they have no auto-tooltip)
- `country_event = { id = <event_id> days = N }` · `news_event = { id = <id> }`

## Triggers (go in condition fields — `available`, `trigger`, `allowed`, `visible`, …)
- `has_country_flag = <flag>` · `has_global_flag = <flag>` · `check_variable = { var = X value = 5 compare = greater_than }`
- `original_tag = <TAG>` · `tag = <TAG>` · `has_government = <group>` · `has_war = yes`
- `date > 1936.6.1` · `has_completed_focus = <focus_id>` · `has_idea = <idea_id>`
- `has_dlc = "<Name>"` · `is_ai = yes` · `has_stability > 0.5` · `NOT = { … }` · `AND/OR = { … }`

## Modifiers (go in `modifier`/`advisor_modifier`/tech `__modifier`; idea `modifier` is a dict)
Flat `key = value` lines. Common ones:
- `political_power_factor = 0.1` · `stability_factor = 0.1` · `war_support_factor = 0.1`
- `research_speed_factor = 0.1` · `production_speed_factor = 0.1` · `consumer_goods_factor = -0.05`
- `army_attack_factor = 0.05` · `army_defence_factor = 0.05` · `army_org_factor = 0.1`
- `justify_war_goal_time = -0.2` · `conscription = 0.02` · `industrial_capacity_factory = 0.1`

## Scopes — who is ROOT / FROM / THIS / PREV inside a field
- In a **focus** `completion_reward` / **decision** `complete_effect`: ROOT = the country doing it.
- In a **targeted decision** (`target_root_trigger`/`target_trigger`, `targets`): ROOT = the taker,
  **FROM = the current target**. To act on the target: `set_autonomy = { target = FROM … }` at ROOT scope.
- In an **event**: ROOT = the country the event fired for; FROM = the sender (if fired from another scope).
- Open a scope inside any field: `every_country = { limit = { … } … }` · `owner = { … }` ·
  `<TAG> = { … }` · `event_target:<key> = { … }` (set the target first with `save_event_target_as`).
- THIS = the current scope; PREV = the enclosing scope one level out.

> Anything here is a starting vocabulary. When you need a token that isn't listed, write it as HOI4 spells
> it, POST it, and run the platform validate/lint — that's faster and more reliable than memorizing the
> full dictionary, and the lint knows your platform version.
