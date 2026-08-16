# Focus-tree fields — `/focus-trees` + nested `/focus-trees/{tree_id}/nodes`

## Tree (`POST /api/projects/{pid}/focus-trees`)
| Field | Meaning |
|---|---|
| `tree_id` | id of the tree (used by `load_focus_tree`). ⚠️ avoid colliding with a vanilla tree id — the platform warns |
| `country_tag` | owner tag (which country sees this tree) |
| `is_default` | exactly one default tree total |
| `tree_kind` | `primary` (a country's tree) or `shared_pool` (shared focus source) |
| `continuous_focus_position_x` / `_y` | pixel position of the continuous-focus menu |
| `initial_show_position` | tagged union — the camera position the tree opens on: `{"kind":"focus","focus_id":"<id>"}` or `{"kind":"coordinates","x":N,"y":N,"offsets":[...]}`. Replaces `initial_show_focus` (still accepted as a compatibility input, but new clients should write this field). |

## Node (`POST /api/projects/{pid}/focus-trees/{tree_id}/nodes`)
| Field | Type / meaning |
|---|---|
| `focus_id` | unique id. ⚠️ re-POSTing the same tree silently makes `<focus_id>_1` duplicates — DELETE orphans |
| `name` | display name (or set `name_en`/`name_zh` for loc) |
| `icon` | `GFX_goal_*` sprite name (reuse a vanilla one, or upload via `nodes/{id}/upload-icon`) |
| `cost` | focus time in "focus points" (÷ by the 7-day tick → weeks; vanilla 10 = 70 days) |
| `x` / `y` | grid position. **Left-anchored** — shift all nodes so min-x ≈ 4 (flag ornament overlaps low-x); on a **continuous-focus tree** shift to **min-x ≈ 12** (the vanilla continuous-focus panel is ~8-9 columns wide). Layout recipe → **hoi4-build-focus** |
| `relative_position_id` | position this node relative to another focus id |
| `prerequisites` | **`list[list[str]]`** — outer = AND, inner = OR. `[["a"]]` needs a; `[["a","b"]]` needs a OR b |
| `mutually_exclusive` | **`list[str]`** of focus_ids — list the OTHER branch entries on each entry node |
| `completion_reward` | **raw effect script** (export wraps as `completion_reward = { … }`) |
| `select_effect` | **raw effect script** — fires when the focus is selected (not completed) |
| `available` | **raw trigger** — when the focus can be started |
| `bypass` | **raw trigger** — auto-complete-and-skip when true |
| `cancel` | **raw trigger** — abandon the focus when true |
| `ai_will_do` | AI weighting body (`factor = 1 modifier = { … }`) |
| `cancel_if_invalid` / `continue_if_invalid` / `available_if_capitulated` | bools (defaults: yes / no / no) |
| `will_lead_to_war_with` | `list[str]` of TAGs (AI war-planning hint) |
| `name_en` / `name_zh` | loc for key `<focus_id>` |
| `desc_en` / `desc_zh` | loc for key `<focus_id>_desc` |
| `effect_tooltip_locs` | dict `{lang: text}` — export injects `custom_effect_tooltip = <focus_id>_et_tt` (use for variable/flag rewards that have no auto-tooltip) |
| `text_icon` | decorative text-icon token |

Raw-script fields → see `_raw-script-fields.md`; token vocabulary → `tokens.md`.

### Common quirks
- **`research_bonus = {…}` is NOT a valid completion_reward effect** — use
  `add_tech_bonus = { bonus = N uses = N category = <cat> }` for a one-shot research boost.
- The primary country does NOT auto-load its own tree by tree-scoring alone in a multi-tree project — if
  several trees overlap in-game, make sure each tree's `country_tag` is its real owner.
