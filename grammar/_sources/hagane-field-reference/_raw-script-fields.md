# Raw-script fields — the one idiom that runs through the whole API

Some platform fields hold a **raw fragment of HOI4 script as a string**. You store the *inner* text; the
export **wraps** it in the correct block. You never write the wrapper, the file, or the filename — the
platform owns those.

**Example.** You PUT the focus field:
```
completion_reward = "add_stability = 0.05\nadd_political_power = 100"
```
The export emits, in the right file, under the right focus:
```
completion_reward = {
    add_stability = 0.05
    add_political_power = 100
}
```

So filling a raw-script field = writing the **inner tokens** (effects, triggers, or modifiers depending
on the field). The token vocabulary is in `tokens.md`.

## Which fields are raw-script, per workbench

| Workbench | Effect fields (take **effect** tokens) | Trigger/condition fields (take **trigger** tokens) | Modifier fields |
|---|---|---|---|
| **Focus node** | `completion_reward`, `select_effect` | `available`, `bypass`, `cancel` | — |
| **Event** | `immediate`, `after`, `mean_time_to_happen`* | `trigger` | — |
| **Event option** | `effects`, `hidden_effects` | `trigger` | — |
| **Idea / spirit** | `on_add`, `on_remove`, `do_effect` | `allowed`, `available`, `visible`, `cancel`, `allowed_civil_war`, `allowed_to_remove` | `modifier` (dict, see ideas.md) |
| **Decision** | `complete_effect`, `remove_effect`, `cancel_effect`, `timeout_effect`, `activation` | `allowed`, `available`, `visible`, `cancel_trigger`, `target_root_trigger`, `target_trigger`, `custom_cost_trigger` | `modifier` (raw flat string) |
| **Decision category** | — | `allowed`, `visible` | — |
| **Character** | `advisor_on_add`, `advisor_on_remove` | `military_visible`, `advisor_available`, `advisor_visible`, `operative_available`, `scientist_visible` | `advisor_modifier` (raw flat) |
| **Custom trait** | — | — | `modifier` (**dict**), `targeted_modifier` (list of `{tag, modifier}`) |
| **Dynamic modifier** | — | `enable`, `remove_trigger` | `modifier` (**dict**) |
| **Super-event option** | `effect` (per option) | — | — |
| **Scripted snippet** | `body` (when `kind=effect`) | `body` (when `kind=trigger`) | — |
| **Technology** | `on_research_complete` | `allow`, `allow_branch`, `on_research_complete_limit` | `modifiers` = `{"__modifier":"<raw flat text>"}` (escape-hatch; a flat `{stat:val}` dict is silently ignored) |
| **MIO** | — | `allowed`, `available`, `visible` | (per-trait `modifier`/`equipment_bonus` nested inside `traits` entries) |
| **Special-project** | — | `allowed`, `visible`, `available` | — (`resource_cost`, `project_output`, `complexity`, `prototype_time` are free-text raw-script too) |
| **Intelligence-agency** | — | `default_trigger`, `available` | — |
| **Autonomy-state** | — | `rule` (raw autonomy-rule block) | `modifier` (**dict**) |
| **Wargoal** | — | `allowed`, `available`, `take_states`, `puppet`, `liberate` | — (`advanced_raw_script` is a free-text escape hatch for anything not covered by the typed fields — see `wargoals.md`) |

Workbenches with **no** raw-script fields (structured/metadata only): countries, bookmarks, history-files
(has an advanced generic `raw_script` escape-hatch only), scripted-localisations (its `body` is a raw
`defined_text` block, not an effect/trigger), equipment, division-templates, division-deployments, states,
doctrines (its modifier/milestone content rides in `raw_extras` — see `doctrines.md`), opinion-modifiers
(all scalar/typed — see `opinion-modifiers.md`), modifier-definitions (all typed/enum — see
`modifier-definitions.md`).

\* `mean_time_to_happen` holds the inner MTTH body (`days = N modifier = { … }`); only meaningful when the
event is **not** `is_triggered_only`.

## Two shapes of "modifier"
- **Idea `modifier`** = a **dict** `{stat: value}` (e.g. `{"stability_factor": 0.1}`). Export renders it
  as a `modifier = { … }` block. See ideas.md.
- **Decision `modifier` / character `advisor_modifier` / tech `__modifier`** = a **raw flat string**
  (e.g. `"political_power_factor = 0.1"`). See tokens.md → Modifiers.

## Rules for writing raw-script fields
- Write tokens exactly as HOI4 spells them (see `tokens.md`); the platform lint checks a curated subset,
  the in-game `error.log` is the final gate.
- Newlines separate statements inside a field (`"add_stability = 0.05\nadd_war_support = 0.05"`).
- Scopes matter: inside these fields you can open a scope (`FROM = { … }`, `every_country = { … }`,
  `owner = { … }`). See `tokens.md` → Scopes for who ROOT/FROM/THIS/PREV are in each field's context.
- A cross-ref to another entity you built (an event id, a focus id) must exist, or the export silently
  drops it — run validate (see `README.md`).
