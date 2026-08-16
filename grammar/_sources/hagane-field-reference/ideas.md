# Idea / national-spirit fields — `/ideas`

National spirits, designers, and country ideas all live here (`idea_type` distinguishes them).

| Field | Type / meaning |
|---|---|
| `idea_id` | unique id |
| `country_tag` | owning country (blank = generic/shared) |
| `idea_type` | `country` (national spirit) / `hidden_ideas` / `tank_manufacturer` / `ship_manufacturer` / `aircraft_manufacturer` / `materiel_manufacturer` / `industrial_concern` / `theorist` … |
| `name` | display name (or use `name_en`/`name_zh`) |
| `picture` | sprite name — **DROPS the `GFX_idea_` prefix** (put `generic_build_infrastructure` for `GFX_idea_generic_build_infrastructure`). Blank → "?" placeholder |
| `modifier` | **dict** `{stat: value}` (e.g. `{"stability_factor": 0.1, "political_power_factor": -0.05}`) — export renders `modifier = { … }` |
| `removal_cost` | PP to remove (default -1 = not removable) |
| `cost` | PP to activate (vanilla `cost =`; 0 = unset) |
| `allowed` | **raw trigger** — which countries can ever have it (evaluated at game start) |
| `available` | **raw trigger** — dynamic availability |
| `visible` | **raw trigger** — show/hide |
| `cancel` / `allowed_to_remove` / `allowed_civil_war` | **raw triggers** |
| `on_add` / `on_remove` / `do_effect` | **raw effects** |
| `is_designer` | designer-type idea |
| `research_bonus` | dict for designer research bonuses |
| `designer_traits` | `list[str]` |
| `targeted_modifier` | `list[dict]` — modifiers targeting another country |
| `equipment_bonus` | dict — per-equipment stat bonus |
| `rule` | dict — `{can_declare_war: no, …}` style rules |
| `level` / `ledger` | manufacturer level / ledger tab |
| `cancel_if_invalid` | drop the idea if its trigger goes false |
| `auto_attach_on_start` | **default `true`** = attached to the country at game start. Set **`false`** to keep an endgame/reward spirit dormant until a focus/event `add_ideas` it |
| `name_en` / `name_zh` / `desc_en` / `desc_zh` | loc |

Raw-script fields → `_raw-script-fields.md`; modifier stats → `tokens.md`.

### Common quirks
- A country-specific spirit still needs `allowed = "original_tag = <TAG>"` if you don't want other
  countries to be able to receive it via generic effects.
- Fill `picture` — a spirit with no picture shows a "?" in the political screen (modifier still applies).
