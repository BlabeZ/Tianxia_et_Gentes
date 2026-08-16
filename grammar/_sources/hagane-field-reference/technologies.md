# Technology fields — `/technologies`

Author custom / overriding research technologies: nodes, prerequisites, unlocks, granted modifiers, and
tree placement.

> 🔴 **Not recommended right now — a custom tech will not appear in the tech tree.** Verified in-game
> (2026-08-07, live game load, not just the exported files): HOI4's tech UI only renders techs that sit
> inside one of a fixed set of vanilla "grid boxes" declared in `interface/countrytechtreeview.gui`; the
> platform doesn't yet emit any grid-box declaration of its own, so a custom tech has nowhere to render.
> This affects **every** custom tech regardless of `folder`, `prerequisites`, or `dependencies` — neither
> connects a new tech to a grid box, only the vanilla side of a `path = { leads_to_tech = ... }` link
> can. About half fail loudly (`Found no grid box for tech <id>` in `logs/error.log`); the other half —
> anything placed in a folder a DLC has replaced (`armour_folder` under No Step Back, `air_techs_folder`
> under By Blood Alone, …) — fail **silently**, no error at all. A fix is planned (a platform-emitted
> grid-box overlay) but not shipped. Until then, treat this workbench as read/preview-only: the fields
> below are accurate, but don't ship a mod whose gameplay depends on a player researching a
> platform-built tech.

| Field | Meaning |
|---|---|
| `tech_id` | unique per-project id (auto-derived from `name` lowercased if blank; auto-suffixed on collision). Ownership is inferred from the id **prefix** (`USA_…`) — the `country_tag` column stays empty for a global tech |
| `country_tag` | `""` = global tech (vanilla default) |
| `tech_line` | logical line (`infantry` / `armor` / `artillery` / `naval` / …) → mapped to an in-game folder |
| `folder` | in-game tech-tree folder id. ⚠️ **armour = the British spelling `armour_folder`** (`armor_folder` → in-game error); air = `air_techs_folder`. Defaults from `tech_line` |
| `research_cost` | research-time cost multiplier (default 1.0) |
| `start_year` | earliest research year / tree column (default 1936) |
| `position_x` / `position_y` | node grid coordinates (⚠️ `position_y` is transformed on export — verify placement in-game, can't check offline) |
| `position_y_is_explicit` | row intent: `true` emits the stored row (including `0`); `false` derives from `start_year`; legacy `null` rows use the line compatibility heuristic |
| `prerequisites` | `list` of required tech_ids |
| `categories` | tech-category tags (drive category-scoped bonuses) |
| `modifiers` | granted modifiers — **see the shape note below** |
| `enable_equipments` | equipment archetypes unlocked (siblings: `enable_subunits` / `enable_equipment_modules` / `enable_building` / `enable_tactic`) |
| `doctrine` | bool — marks the node as a doctrine tech |
| `xp_research_bonus` | dict — XP-boosted research bonus |
| `on_research_complete` | **raw effect** — runs when researched |
| `allow` / `allow_branch` / `on_research_complete_limit` | **raw triggers** |
| `ai_will_do` | AI weight body (`factor = 1`), NOT an effect |
| `name` | ⚠️ defaults to the literal `"New Technology"` — **set `name = <tech_id>`** or the bareword rides into the output |

### 🔴 The `modifiers` shape (a flat dict is silently ignored)
`modifiers` is a dict, but the shape matters:
- **A flat country modifier on the tech** → use the escape-hatch key:
  `modifiers = {"__modifier": "army_attack_factor = 0.05\nresearch_speed_factor = 0.1"}`.
- **Per-equipment bonuses** → nested `{archetype: {stat: value}}`.
- A plain `{stat: value}` dict is **silently ignored** (tech emits with no modifier). Use `__modifier`.

Raw-script fields → `_raw-script-fields.md`; modifier stats → `tokens.md`.

### Common quirks
- The route `{tech_id}` path param is the **integer DB id**, not the string `tech_id`.
- `add_tech_bonus` category (when unlocking via a focus) must be a real category — `construction` /
  `infrastructure` are NOT categories (use `industry`).
