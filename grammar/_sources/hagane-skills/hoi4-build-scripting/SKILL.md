---
name: hoi4-build-scripting
description: Use when filling the HOI4 mod platform's **scripting & modifiers** surfaces — scripted effects / scripted triggers (reusable named script blocks), scripted localisation (`defined_text` dynamic loc), dynamic modifiers, custom leader/commander/scientist traits — or shipping the four no-workbench raw-template domains: defines / engine constants, balance of power, radio station / music, peace-conference tuning. Carries the modifier SHAPE rule (dict vs raw flat string), the call-by-name dispatch idioms, and the template→edit flow. Invoke whenever creating/editing these via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Scripting & Modifiers

> **A "build card" = the thin bridge between the platform form, the HOI4 output, and the player
> experience.** It does NOT re-teach the full field tables — `field-reference/scripted-snippets.md`,
> `scripted-localisations.md`, `dynamic-modifiers.md`, `custom-traits.md`, `defines.md`,
> `balance-of-power.md`, `music.md` and `peace-conference.md` already map every field, and
> `field-reference/tokens.md` / `_raw-script-fields.md` cover token legality and which fields hold raw
> script. This card carries the per-domain quirks, the cookbook, the wiring, and the validation
> discipline.
>
> Route table / transport / PAT auth → **hoi4-build-api**. Scope passing (scripted blocks run in the
> CALLER's scope — THIS/ROOT/FROM travel with the call site) → **hoi4-wiring**.

## 0. Before you fill anything — two validation sources
1. **Read the matching `field-reference/*.md`** (listed above) for the exact field shapes. For the four
   raw-template domains (defines / bop / music / peace-conference) the field-reference file IS the spec —
   there is no workbench form to GET.
2. **Validate EVERY token** you put in a raw field (`body`, `enable`, `remove_trigger`, `ai_will_do`,
   and everything inside a template file). Token legality lives in `field-reference/tokens.md`; the
   platform checks a curated set at export (`POST /api/projects/{pid}/export/validate` +
   `GET /api/lint/tree-validation/{pid}`); the in-game `logs/error.log` is the final gate for anything
   the lint can't know. Remember: a scripted snippet has NO scope of its own — its tokens must be legal
   in the scope of every call site (§3).

## 1. Platform form → HOI4 output (per sub-workbench)

### 🔴 The one cross-cutting rule: two shapes of "modifier"
| Where | Shape |
|---|---|
| idea `modifier` · **dynamic-modifier `modifier`** · **custom-trait `modifier`** | **dict** `{stat: value}` — export renders the `modifier = { … }` block |
| decision `modifier` · technology modifiers | **raw flat string** (`"political_power_factor = 0.1"`) |

Mixing them is the #1 silent failure in this domain: a raw string where a dict is expected (or vice
versa) 422s at best, no-ops at worst. Full table → `field-reference/_raw-script-fields.md`.

### Scripted snippets — `/scripted-snippets`
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `kind` (`effect` \| `trigger`, default `effect`) | a named `scripted_effects` vs `scripted_triggers` block | Picks the target file family AND what tokens `body` may hold. |
| `name` | the block name — the dispatch symbol | Internal symbol, no loc. Unique per project + kind (duplicate → 409). Call it from ANY effect/trigger field as `<name> = yes`. |
| `body` | **raw inner script**, verbatim inside the braces | Effect tokens when `kind=effect`, trigger tokens when `kind=trigger` — never mix. |

The platform's read-only **scripted-symbols index** (`GET /api/projects/{pid}/scripted-symbols`)
catches used-but-undefined names and name collisions — check it after wiring calls in.

### Scripted localisations — `/scripted-localisations`
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `name` | the `defined_text` dispatch symbol | Referenced from loc VALUES as `[GetX]`-style calls, not from script fields. |
| `body` | the **verbatim inner `defined_text` block** | 🔴 The body **re-includes the `name = X` line itself** — it is neither an effect nor a trigger body; write it exactly as HOI4 spells a `defined_text`. No `kind` field (one entity type). Duplicate `name` → 409. |

The displayed strings live in the localisation entries the body's `text = { … }` branches point at —
the scripted-localisation itself carries no player-facing text.

### Dynamic modifiers — `/dynamic-modifiers`
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `dm_id` | the modifier's name | Trimmed; auto-suffixed on collision; colliding with a vanilla id = warn-and-allow. |
| `enable` / `remove_trigger` | raw **trigger** blocks | Trigger-gated at runtime: `enable` = when it applies, `remove_trigger` = when it auto-removes. |
| `modifier` | `modifier`-block stats | **dict** (see the rule above). |
| `icon` / loc fields | tooltip sprite + name/desc | Fill both languages. |

🔴 **Defining it does nothing by itself** — a dynamic modifier only exists on a country after some
effect runs `add_dynamic_modifier = { modifier = <dm_id> }` (from a focus reward, event option,
decision effect…). Remove with `remove_dynamic_modifier`. → §3.

### Custom traits — `/custom-traits`
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `trait_type` | `country_leader` / `unit_leader` / `scientist` trait | Server-validated enum. |
| `trait_id` | the trait TOKEN | 🔴 The route's `{id}` path param is the integer DB id; the body's `trait_id` is the string token — don't conflate. |
| `modifier` / `targeted_modifier` | trait modifiers | `modifier` = **dict**; `targeted_modifier` = `list[dict]` of `{tag, modifier}`. |
| `ai_will_do` / `random` | AI-assignment weight | Raw AI-weight script (`factor = 1 modifier = { … }`). |
| loc fields | trait name/desc | Name defaults to the cleaned `trait_id` if blank. |

Characters then reference the token in `traits` / `advisor_traits` — those are two different lists
(→ **hoi4-build-characters**). `GET /custom-traits/known` = vanilla ∪ project autocomplete set.
Icon upload is unit_leader / scientist only; a country_leader "icon" is a numeric sprite index.

### The four no-workbench domains — template first, then edit
Defines, balance of power, music, and peace-conference tuning have **no workbench**; the supported
path for these four is the raw-file **template flow**:
1. **List** the template catalogue — MCP `list_raw_templates` / REST
   `GET /api/projects/{pid}/raw-files/templates`.
2. **Create** from the domain's template — MCP `create_raw_from_template(template=…, key=…)` / REST
   `POST /api/projects/{pid}/raw-files/from-template/{defines|bop|music|peace-conference}` with
   `{key}` (lowercase `a-z0-9_`, 2–40 chars). This drops a correct, commented skeleton at the right
   in-mod path.
3. **Edit** the dropped file's content via `PUT /api/projects/{pid}/raw-files/{id}` (list
   `GET /raw-files` to find the id). Re-running the same template upserts rather than duplicating.

| Domain | Template drops | What you actually mod |
|---|---|---|
| `defines` | `common/defines/{key}_tweaks.lua` | **Per-key Lua overrides** (`NDefines.<NS>.<KEY> = value`, one per line, no commas). 🔴 Never ship a copied vanilla defines file; 🔴 never hand-write `START_DATE`/`END_DATE` — the start date lives in project settings and changing it cascades (the platform emits the timeline define itself; a hand-written one double-defines it and the lint flags the conflict). |
| `bop` | `common/bop/{key}_bop.txt` | Root block name = the BoP id; sides + ranges with `modifier`/`rule`/`on_activate`/`on_deactivate`. The file alone is inert — wiring in §3. |
| `music` | `music/{key}_music.asset` + `.txt` **pair** | `.asset` = song defs (name/file/volume), `.txt` = station header + weighted `chance` blocks. Upload each `.ogg` via `POST /raw-files/binary` (multipart, ≤ 25 MiB) to the same `music/` folder. `music_station = "base_music"` joins the vanilla station; a NEW station id additionally needs `.gui` + 2-frame sprite + loc (see `field-reference/music.md`). |
| `peace_conference` | `common/peace_conference/cost_modifiers/{key}_peace_cost_modifiers.txt` | Cost multipliers per action (`take_states`/`puppet`/`force_government`/`liberate`) gated by `enable` triggers. AI-desire (`ai_peace/`) and category (`categories/`) files follow the shapes in `field-reference/peace-conference.md`. Global base costs are defines (`NDiplomacy.PEACE_*`). |

## 2. Want experience X → fill fields Y (cookbook)
- **One effect, called from five focuses** → POST a snippet `{kind:"effect", name:"mymod_purge_army",
  body:"army_experience = -50\nadd_stability = -0.05"}`; each focus `completion_reward` just says
  `mymod_purge_army = yes`. Edit the snippet once, all five callers change.
- **A reusable condition** → `{kind:"trigger", name:"mymod_is_stable_democracy",
  body:"has_government = democratic\nhas_stability > 0.6"}`; use `mymod_is_stable_democracy = yes`
  in any `available`/`visible`/`trigger` field (all conditions inside AND together).
- **A title that changes with ideology** → POST a scripted localisation whose body is a full
  `defined_text` (its `name = …` line included) with `text = { trigger = { has_government = X }
  localization_key = <key> }` branches; then write `[Root.GetMymodTitle]`-style calls (your `name`)
  inside the loc VALUES of events/focuses/ideas.
- **A creeping national penalty that heals itself** → POST a dynamic modifier
  `{dm_id, enable:"has_country_flag = mymod_crisis", remove_trigger:"has_stability > 0.7",
  modifier:{"consumer_goods_factor":0.10}, icon, name_en/zh}`; apply from an event option's `effects`:
  `add_dynamic_modifier = { modifier = <dm_id> }`. It auto-drops when stability recovers.
- **A bespoke leader trait** → POST `{trait_type:"country_leader", trait_id:"mymod_iron_chancellor",
  modifier:{"political_power_factor":0.15}, name_en/zh}`; then add `mymod_iron_chancellor` to the
  character's `traits` (country_leader traits have no custom icon — sprite index only).
- **An internal power-struggle bar** → template `bop` → edit ranges/sides → activate from a focus
  reward with `set_power_balance = { id = <bop_id> }`, push it from later focuses/events with
  `add_power_balance_value = { id = … value = -0.1 tooltip_side = <side_id> }` (§3).
- **Slower research, longer events, 3 base slots** → template `defines`, keep ONLY the keys you
  change (`NDefines.NCountry.BASE_RESEARCH_SLOTS = 3` …), restart the game to test — defines are
  load-time and cannot be flipped by script.
- **A mod soundtrack** → template `music` with `music_station = "base_music"`, upload the `.ogg`s via
  the binary route, add a `name:0 "Track Title"` loc line per song, weight war tracks with
  `chance = { base = 1 modifier = { factor = 2 has_war = yes } }`.
- **"Liberate is too expensive for my democracies"** → template `peace_conference`; entry with
  `peace_action_type = liberate`, `enable = { ROOT = { has_government = democratic } }`,
  `cost_multiplier = 0.5`. Steer the AI the same way via an `ai_peace/` file (`ai_desire` sums;
  ≤ 0 total = the AI never bids it).

## 3. Wiring out (→ hoi4-wiring)
- **Snippets run in the CALLER's scope.** `<name> = yes` executes the body exactly where it's written —
  THIS/ROOT/FROM are the call site's, and a body token that's country-scope-only breaks any state-scope
  caller. Write bodies for the narrowest scope you'll call from, or open explicit scopes inside.
- **Dynamic modifiers travel by effect**: `add_dynamic_modifier = { modifier = <dm_id> }` /
  `remove_dynamic_modifier = { modifier = <dm_id> }` from focus rewards, event options, decision
  effects. `enable` then gates whether the applied modifier is currently active.
- **BoP is a three-part contract**: ship the file (§1) → **activate** with
  `set_power_balance = { id = … }` (country history, focus reward, or event option — until this runs
  the bar is invisible) → **push/react** with `add_power_balance_value`,
  `add_power_balance_modifier`, and the triggers `has_power_balance` / `power_balance_value` /
  `is_power_balance_in_range = { id = … range = <range_id> }` / `is_power_balance_side_active` in any
  raw trigger field.
- **Scripted-loc calls live in loc text, not script**: reference the `name` from
  `title`/`desc`/tooltip loc values; a typo'd call renders as literal bracket text in-game — proofread
  in the in-game check.
- **Custom traits close the loop through characters**: trait token → character `traits` /
  `advisor_traits` → **hoi4-build-characters** for the two-list trap and dual-role merging.

## 4. Self-check after building (entity-level)
GET your entities back and assert: every snippet/scripted-loc **name referenced from any raw field or
loc value actually exists** (read `GET /scripted-symbols` — used-but-undefined = a silent in-game
no-op); dict-vs-raw modifier shapes match §1; every dynamic modifier has at least one
`add_dynamic_modifier` caller; every BoP has a `set_power_balance` activator; defines file contains
only changed keys and no date defines; each `.txt` music entry's `song` matches an `.asset` `name`
and the `.ogg` is uploaded. Then run `POST /api/projects/{pid}/export/validate` +
`GET /api/lint/tree-validation/{pid}` before the in-game pass.

## 5. Common traps (distilled)
- 🔴 **Modifier shape**: dynamic-modifier / custom-trait / idea `modifier` = **dict**; decision /
  technology modifiers = **raw flat string**. Don't carry one domain's habit into another.
- 🔴 A snippet body written for the wrong scope fails at SOME call sites only — the same name can work
  from a focus and break from a state event. Validate per call site.
- 🔴 A defined/never-applied dynamic modifier, or a BoP with no `set_power_balance`, is 100% inert —
  the file/entity existing changes nothing in-game.
- 🔴 A typo'd Lua define key assigns silently — no error, no effect. Copy key names verbatim from
  vanilla's defines list; never ship a whole copied defines file; never hand-write the start-date
  defines (project settings own the timeline).
- 🔴 Custom-trait routes: path param = integer DB id, body `trait_id` = string token.
- Scripted-localisation `body` re-includes its own `name = X` line — omitting it emits a nameless
  `defined_text`.
- A wrong `music_station` header (or a renamed non-Vorbis "`.ogg`") fails silently — no song, no error.
- Peace-conference triggers read the PRE-conference world mid-conference — use the `pc_*` trigger
  family for anything decided during the conference; cost multipliers multiply (stay ≈ 0.4–3.0).
- Duplicate `(kind, name)` snippet or duplicate scripted-loc `name` → 409 (edit the existing one
  instead of retrying create).

## Cross-links
- Route table / transport / PAT auth (`HOI4_PLATFORM_URL` + `Authorization: Bearer` from
  `HOI4_PLATFORM_TOKEN`) → **hoi4-build-api**.
- Field shapes + token legality → `field-reference/scripted-snippets.md` ·
  `scripted-localisations.md` · `dynamic-modifiers.md` · `custom-traits.md` · `defines.md` ·
  `balance-of-power.md` · `music.md` · `peace-conference.md` · `_raw-script-fields.md` · `tokens.md`.
- Scope passing, flags/variables, and cross-entity chains (who calls the snippet, what applies the
  modifier, what pushes the BoP) → **hoi4-wiring**.
- The callers themselves: decision/idea effects → **hoi4-build-decisions-ideas**; event options →
  **hoi4-build-events**.
- Validate on the platform (`POST export/validate` + `GET lint/tree-validation`); the in-game
  `error.log` is the final gate → **hoi4-investigate**.
