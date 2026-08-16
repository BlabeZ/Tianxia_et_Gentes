# Decision fields — `/decisions` + nested `/decisions/categories`

## Category (`POST /api/projects/{pid}/decisions/categories`)
| Field | Meaning |
|---|---|
| `category_id` | unique id (⚠️ platform warns on vanilla collision) |
| `icon` / `picture` | category art |
| `priority` | sort order |
| `allowed` | **raw trigger** — which countries see the category (set `original_tag = <TAG>` to restrict!) |
| `visible` | **raw trigger** — dynamic show/hide |
| `on_map_area` | **raw** inner block for a map-area category |
| `visibility` | `visible` / `solo` / `hidden` |
| `name_en` / `name_zh` / `desc_en` / `desc_zh` | loc |

## Decision (`POST /api/projects/{pid}/decisions`)
| Field | Type / meaning |
|---|---|
| `category_id` | **int FK** to the category (not a string!) |
| `decision_id` | unique id |
| `icon` | decision icon |
| `allowed` | **raw trigger** — static country restriction (`original_tag = <TAG>` — decisions are GLOBAL by default) |
| `available` | **raw trigger** — when takeable (shows greyed if false) |
| `visible` | **raw trigger** — show/hide entirely |
| `cost` | PP cost |
| `fire_only_once` | one-shot |
| `cancel_if_not_visible` | cancel an active timed decision when `visible` goes false |
| `days_remove` | duration (a timed decision) |
| `days_re_enable` | cooldown before re-take |
| `complete_effect` | **raw effect** — on take |
| `remove_effect` | **raw effect** — when the timer ends |
| `cancel_effect` | **raw effect** — on cancel |
| `cancel_trigger` | **raw trigger** — auto-cancel condition |
| `modifier` | **raw flat modifier** — active while the decision is running |
| `activation` | **raw effect** — mission activation (mission-flow decisions) |
| `timeout_effect` | **raw effect** — mission timeout |
| `days_mission_timeout` | mission clock |
| `selectable_mission` / `is_good` | mission flags |
| `targeted_modifier` | dict — modifier applied to a target |
| `targets` / `target_array` | `list[str]` — target scope(s) for a targeted decision |
| `target_root_trigger` | **raw trigger** — HIDES the whole decision when false (use `available` to show greyed instead) |
| `target_trigger` | **raw trigger** — per-target filter |
| `state_target` / `highlight_states` / `on_map_mode` | state-targeting + map display |
| `custom_cost_trigger` / `custom_cost_text` | non-PP cost |
| `war_with_on_add` / `war_with_on_remove` | war-flag helpers |
| `ai_will_do` | AI weighting body |
| `effect_tooltip_locs` | dict — export injects `custom_effect_tooltip = <decision_id>_et_tt` (for variable/flag effects) |
| `name_en` / `name_zh` / `desc_en` / `desc_zh` | loc |

Raw-script fields → `_raw-script-fields.md`; tokens → `tokens.md`.

### Common quirks
- **Decisions are GLOBAL by default.** A blank country_tag creates a global decision; a nonblank country_tag on a created decision synthesizes allowed = { original_tag = TAG }.
  Imported or pre-existing row metadata does not add that restriction automatically. A country-specific
  category still needs `visible = "original_tag = <TAG>"`.
- In a **targeted** decision, ROOT = the taker and **FROM = the current target** (see `tokens.md` →
  Scopes) — get the `set_autonomy`/`puppet` direction right.
