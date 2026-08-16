# Balance of power — two-sided struggle bars (`common/bop/*.txt`)

A balance of power (BoP) models an internal struggle between two sides as a bar from **−1 (left) to
+1 (right)**, divided into ranges: whichever range the value sits in applies modifiers/rules to the
country and fires effects on entry/exit. Engine mechanic since 1.12 — vanilla's own BoPs are DLC
content, but the system is script-accessible to mods. There is no BoP workbench: you ship one raw
file, then wire it with effects from focuses / events / decisions.

## Directory & naming rules
- Files: `common/bop/*.txt`. Each **root-level block name = the BoP id** — net-new, e.g.
  `mymod_army_vs_party` (vanilla uses country tags: `SWI.txt`, `ITA.txt` — don't shadow them).
- The platform template writes `common/bop/{key}_bop.txt`.
- Side `icon`s are spriteType refs (`GFX_*`); a custom icon needs a sprite entry in `interface/*.gfx`.

## Root block
| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `initial_value` | decimal −1..1 | no | 0 | starting value of the bar |
| `left_side` / `right_side` | side id | yes | — | the default active sides |
| `decision_category` | category token | no | — | **moves** that decision category into the BoP view |
| `side = { … }` | block ×N | yes | — | `id`, `icon` (GFX), and the side's `range` blocks |
| `range = { … }` | block ×N | yes | — | directly in the root (always live) or inside a `side` (live only while that side is active) |

## Range block
| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | range id | yes | referenced by `is_power_balance_in_range` |
| `min` / `max` | decimal | yes | the interval on the bar this range covers |
| `modifier = { … }` | modifier block | no | applied to the country while the value is inside |
| `rule = { … }` | game rules | no | e.g. `can_create_faction = yes` |
| `on_activate` / `on_deactivate` | **raw effect** | no | fires the instant the value enters / exits the range |

## Minimal working example
The platform's `bop` template drops this shape at `common/bop/{key}_bop.txt`:
```
mymod_army_vs_party = {
    initial_value = 0
    left_side = mymod_army
    right_side = mymod_party

    range = {                     # always-live middle band
        id = mymod_balanced
        min = -0.2
        max = 0.2
        modifier = { stability_factor = 0.05 }
    }

    side = {
        id = mymod_army
        icon = GFX_idea_generic_agrarian_society
        range = {
            id = mymod_army_dominant
            min = -1
            max = -0.2
            modifier = { war_support_weekly = 0.01 }
            on_activate = { add_political_power = 50 }
        }
    }

    side = {
        id = mymod_party
        icon = GFX_idea_generic_degauss_ship_hulls
        range = {
            id = mymod_party_dominant
            min = 0.2
            max = 1
            modifier = { political_power_factor = 0.10 }
        }
    }
}
```

## Wiring — the file alone does nothing
1. **Activate** — `set_power_balance = { id = mymod_army_vs_party }` in country history, a focus
   `completion_reward`, or an event option. Until this runs, the BoP is invisible and inert.
2. **Push** — `add_power_balance_value = { id = … value = -0.1 tooltip_side = mymod_army }`.
3. **Drift** — define a static modifier in `common/modifiers/*.txt` (e.g.
   `mymod_drift = { power_balance_weekly = -0.01 }`) and attach it with
   `add_power_balance_modifier = { id = … modifier = mymod_drift }`; remove with
   `remove_power_balance_modifier` / `remove_all_power_balance_modifiers`.
4. **React** — triggers: `has_power_balance`, `power_balance_value = { id = … value > 0.7 }`,
   `is_power_balance_in_range`, `is_power_balance_side_active`, `has_power_balance_modifier`.

All of these live in raw-script fields (`completion_reward`, event options, decision effects) —
`_raw-script-fields.md` lists which fields take them; token vocabulary in `tokens.md`.

## Platform entry points
- **Template** — MCP `create_raw_from_template(template="bop", key="army_vs_party")` / REST
  `POST /api/projects/{pid}/raw-files/from-template/bop` `{key}` → `common/bop/{key}_bop.txt`
  (key: lowercase `a-z0-9_`, 2–40 chars).
- **Any other path** — REST only: `POST /api/projects/{pid}/raw-files` `{dest_path, content}`.

### Common quirks
- ⚠️ **Defining the BoP is not enough** — no `set_power_balance`, no bar. The #1 "why doesn't it show
  up" answer.
- **Side ranges have dead zones.** A range inside a `side` exists only while that side is active;
  make sure the active sides' ranges plus the root ranges cover every value the bar can reach, or
  stretches of the bar apply nothing.
- **`decision_category` moves, not copies.** The category's decisions disappear from the normal
  decisions list and render inside the BoP view only.
- The value clamps to [−1, 1] — over-pushing is silently capped, sized pushes near the edge lose part
  of their value.
