---
name: hoi4-build-military
description: Use when filling the HOI4 mod platform's **Military & Hardware** workbenches — technology / tech tree, equipment + variants, doctrines, sub-units / battalions, division templates, starting army / OOB, air wings, fleets / navy / task forces / ships, MIO / military industrial organization, special projects, intelligence agency, autonomy / subject levels. The platform-form → in-game bridge + the cookbook + the quirks a GET won't reveal (esp. the tech `__modifier` escape, equipment None-means-inherit, wrapped list GETs, the doctrine discriminator, and the read-modify-write idiom for MIO traits / agency upgrades). Invoke whenever creating/editing any military entity via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Military & Hardware

> **A "build card" = the thin bridge between the platform form, the HOI4 output, and the player
> experience.** It does NOT re-teach the full field tables — `field-reference/technologies.md`,
> `equipment.md`, `doctrines.md`, `sub-units.md`, `division-templates.md`, `division-deployments.md`,
> `oob-units.md`, `mios.md`, `special-projects.md`, `intelligence-agencies.md`, `autonomy-states.md`
> already map every field, and `field-reference/_raw-script-fields.md` / `tokens.md` cover which fields
> hold raw script and which tokens are legal. This card carries the per-workbench emission map, the
> cookbook, the wiring, and the validation discipline.
>
> Route table / transport / auth → **hoi4-build-api**. Cross-entity wiring (focus→tech,
> event→autonomy, on_actions) → **hoi4-wiring**. States, territory, and country history (day-0 start
> state, `oob = "<stem>"`) → **hoi4-build-scenario**.

## 0. Before you fill the form — validation sources
1. **Read the matching `field-reference/<workbench>.md`** for the exact field shapes before POSTing.
   When unsure, GET an existing entity and copy its shape (the protocol in **hoi4-build-api** §1).
2. **Validate every token** you put in a RAW field (tech `on_research_complete` / `allow`, MIO and
   agency and special-project triggers, autonomy `rule`, doctrine `raw_extras`). Token legality lives
   in `field-reference/tokens.md`; the platform checks a curated set at export
   (`POST /api/projects/{pid}/export/validate` + `GET /api/lint/tree-validation/{pid}`); the in-game
   `logs/error.log` is the final gate for anything the lint can't know.
3. **Know your DLC gates** — several military systems only exist for players who own the DLC:
   MIOs = *Trial of Allegiance* · intelligence agencies = *La Résistance* · special projects =
   *Götterdämmerung* · autonomy/subject levels = *Together for Victory* · some tech folders are
   per-DLC. Content in a gated workbench is invisible to players without that DLC — decide whether
   your mod requires it, and say so in your mod description.

## 1. Platform form → HOI4 output, per sub-workbench (short — full tables in field-reference)

### 1.1 Technologies (`/technologies`)
🔴 **Not recommended right now** — custom techs don't render in the tech tree at all, in any folder or
connection shape (confirmed in-game). Full detail → `field-reference/technologies.md`.

| Platform field | Quirk |
|---|---|
| `modifiers` | 🔴 A flat `{stat: value}` dict is **silently ignored** (tech emits with no modifier). Country modifiers go through the escape-hatch key: `modifiers = {"__modifier": "army_attack_factor = 0.05\nresearch_speed_factor = 0.1"}` (raw flat script). Per-equipment bonuses = nested `{archetype: {stat: value}}`. Follow `field-reference/technologies.md` — it has the current wording. |
| `folder` | ⚠️ armour = the **British spelling** `armour_folder` (`armor_folder` → in-game error); air = `air_techs_folder`. |
| `name` | Defaults to the literal `"New Technology"` — set `name = <tech_id>` or the bareword rides into the output. |
| `prerequisites` / `enable_equipments` / siblings | Lists of ids/tokens; `enable_*` is how a tech unlocks equipment / sub-units / modules / buildings / tactics. |
| `on_research_complete` / `allow` / `allow_branch` | RAW effect / triggers. `ai_will_do` is an AI-weight body, NOT an effect. |

### 1.2 Equipment + variants (`/equipment`)
| Platform field | Quirk |
|---|---|
| every numeric stat (`soft_attack`, `build_cost_ic`, …) | 🔴 **All Optional; `None`/omitted = inherit from archetype — do NOT send `0`** (0 is a real override). A variant persists only the columns it explicitly overrides. |
| `is_archetype` / `archetype` / `parent` | `archetype`/`parent` are **string equipment-id refs**, not int FKs. One row per archetype, one per concrete variant/year model. |
| `resources` | dict `{resource: amount}`. |

### 1.3 Doctrines (`/doctrines`)
| Platform field | Quirk |
|---|---|
| `entity_type` | 🔴 The **discriminator** — one table holds four kinds: `folder` / `grand_doctrine` / `track` / `subdoctrine`. What is emitted depends on the type; switching the type keeps stored values but changes/stops their emission (e.g. `xor` emits only while `subdoctrine`). |
| `folder_key` / `track_key` | Parent links are **string keys**, not FKs — no nested routes. |
| `raw_extras` | 🔴 The node's actual bonus content (modifier / milestones / rewards / mastery) has **no typed fields** — it rides in `raw_extras`. GET an existing node to see the shape before authoring. |

### 1.4 Sub-units / battalions (`/sub-units`) — NEW battalion & company types
| Platform field | Quirk |
|---|---|
| `sub_unit_id` | The unit token that division templates reference in `regiments`/`support`. |
| `unit_types` | Emits as HOI4 `type = { … }` (the field is renamed on the platform). |
| `need` / `stats` / `terrain_modifiers` | `need` = dict `{equipment_archetype: amount}`; `stats` = the catch-all dict for root numeric stats (no per-stat columns); `terrain_modifiers` = `{terrain: {modifier: value}}`, standard terrain keys only. |
| the 8 flags (`special_forces`, `marines`, …) | Tri-state: `None` = omit the line (engine default), `False` = an explicit `no`. |

Full table + preview/import routes → `field-reference/sub-units.md`.

### 1.5 Division templates + deployments (`/division-templates` · `/division-deployments`)
| Platform field | Quirk |
|---|---|
| template `regiments` / `support` | `list[dict{token, x, y}]` — the `token` is a sub-unit id (vanilla or yours from §1.4). |
| deployment `division_template` | 🔴 A **name string ref** to a template's `template_name` **within the same `oob_file`** — create the template first, then reference by name. Not an FK. |
| `oob_file` | Shared group stem across templates, deployments, AND the air/naval OOB (§1.6); derives `country_tag` from its prefix. The country's history must point at it (`oob = "<stem>"` → **hoi4-build-scenario**). |
| deployment `location` | A bare province id (int). Provinces live in states — states are **edit-only** (seed from vanilla first); territory setup → **hoi4-build-scenario**. |

### 1.6 Air wings & navy (`/oob-units`) — starting air force + fleets
| Platform resource | Quirk |
|---|---|
| `air-wing-groups` → `air-wings` | Group = one air base (its `location` = the **state id**, required); wings hang off it via `group_id` (**int FK**, unlike §1.5's name ref). Wing `equipment_type` = the plane equipment token. |
| `fleets` → `task-forces` → `ships` | Same int-FK chain (`fleet_id`, `task_force_id`). Fleet `naval_base` / task-force `location` = province ids. Ship `equipment_type` + `amount`/`owner`/`version_name` compose the ship's equipment block; `version_name` names an equipment **variant**. |
| all scalar fields | 🔴 Sent as **strings**, even numbers (`"9601"` not `9601`) — they are script tokens, validated on write (invalid → 422). Empty string = omit the line. |
| `snapshot` / `preview` | `GET /oob-units/snapshot` returns the whole five-collection hierarchy in one object; `GET /oob-units/preview` returns the generated script — proofread it before export. |

Full tables + routes → `field-reference/oob-units.md`.

### 1.7 MIOs (`/mios`) — *Trial of Allegiance DLC*
| Platform field | Quirk |
|---|---|
| `traits` | 🔴 One JSON list, **no per-trait routes or ids** — to add a trait: **GET the MIO, append to `traits`, PUT the whole list back** (read-modify-write; never overwrite what's there). Per-trait icons are keyed by the trait's `token`. |
| `allowed` / `available` / `visible` | RAW triggers — `allowed` is the static gate for which countries get the MIO. |
| list GET | 🔴 Returns a **wrapped** object `{"mios":[…]}` — unwrap or `len()` reads 0. |

### 1.8 Special projects (`/special-projects`) — *Götterdämmerung DLC*
🔴 **Not recommended right now** — exports can produce a file HOI4's parser rejects outright; root
cause not yet found. Full detail → `field-reference/special-projects.md`.

| Platform field | Quirk |
|---|---|
| nested resources | `/specializations` (tracks/facility types) + `/projects` (DAG nodes) + `/validate`. |
| `special_project_parent` / `specialization` | DAG edges are **string token refs**, not FKs. |
| `complexity` / `prototype_time` / `resource_cost` / `project_output` | Free-text **raw-script** strings, not typed numbers. Run `/special-projects/validate` to catch missing parents / cycles before export. |

### 1.9 Intelligence agencies (`/intelligence-agencies`) — *La Résistance DLC*
| Platform field | Quirk |
|---|---|
| `names` | `list[str]` — the engine picks one at random. No description slot exists. |
| `upgrade_branches` | 🔴 One `list[dict]` with **no dedicated add endpoint** — same read-modify-write idiom as MIO traits: GET, append, PUT back. |
| logo | Ship a real upload (`upload-logo`) — a base-sprite ref won't ship. |
| list GET | 🔴 Wrapped: `{"agencies":[…],"total":N}` — unwrap. |

### 1.10 Autonomy states (`/autonomy-states`) — *Together for Victory DLC*
| Platform field | Quirk |
|---|---|
| `modifier` | A **dict** `{stat: value}` (like ideas) — NOT a raw flat string. |
| `min_freedom_level` | 🔴 Stored as an **int = freedom × 1000** (freedom 0.25 → send `250`); the export restores the decimal. |
| `rule` | RAW autonomy-rule block (`can_be_target` / `can_take_level` / …). |
| list GET | 🔴 Wrapped: `{"autonomy_states":[…]}` — unwrap. |

## 2. Want experience X → fill fields Y (cookbook)
- **A researchable tech that buffs the army** → 🔴 **not recommended right now** (see
  `field-reference/technologies.md`): custom techs don't render in the tech tree at all today,
  confirmed in-game, not a display nitpick. If you build one anyway, the shape is `name=<tech_id>`,
  `folder` (mind `armour_folder`), `research_cost`, `start_year`, `position_x/y`,
  `prerequisites=[…]`, `modifiers={"__modifier": "army_attack_factor = 0.05"}` — expect it to be
  invisible to players regardless.
- **A new weapon with year models** → one equipment row `is_archetype=True` with the full stat block,
  then variant rows with `archetype=<id>`, `year`, and ONLY the stats that change (everything else
  `None` = inherited). Unlock each via a tech's `enable_equipments`.
- **A custom battalion type** → POST a sub-unit: `sub_unit_id`, `group` (recruit tab), `categories`,
  `unit_types`, `need={<equipment>: N}`, `stats={…}`, `terrain_modifiers={…}`, `active` or unlock via
  a tech's `enable_subunits`. Then use its token in a division template's `regiments`.
- **A starting army** → division template (`oob_file="TAG_1936"`, `regiments`/`support` grids) →
  N deployments referencing `division_template` by NAME with `location=<province>`, `count`,
  `start_equipment_factor`. Make sure the country history uses that `oob_file` → **hoi4-build-scenario**.
- **A starting air force** → air-wing-group at `location="<state id>"` (same `oob_file`), then wings
  with `equipment_type="<plane equipment>"`, `amount="100"`, optional `owner`/`name`.
- **A starting navy** → fleet (`naval_base="<province>"`) → task-force (`location="<province>"`) →
  ships (`definition="destroyer"`, `equipment_type="<hull/type token>"`, `amount="1"`, `owner="<TAG>"`,
  `version_name="<variant name>"`). Preview the script, then export.
- **A national arms manufacturer** → MIO with `mio_id`, `equipment_type=[…]`,
  `research_categories=[…]`, `allowed="original_tag = <TAG>"`, initial `traits=[…]`; later traits via
  read-modify-write. (A tank/ship/plane **designer company** is an IDEA with a designer slot, not a
  MIO → **hoi4-build-decisions-ideas**.)
- **A doctrine branch** → build the hierarchy top-down with `entity_type`: `folder` → `grand_doctrine`
  → `track`(s) → `subdoctrine`(s), linking by `folder_key`/`track_key`; carry each node's bonuses in
  `raw_extras` (GET a vanilla-shaped node first to copy the block shape).
- **A wunderwaffe program** → 🔴 **not recommended right now** (see
  `field-reference/special-projects.md`): exports can currently produce a file HOI4's script parser
  rejects outright, not yet root-caused. If you build one anyway: specialization first, then project
  nodes with `special_project_parent` edges, raw `resource_cost`/`project_output`;
  `/special-projects/validate` catches DAG problems but **not** this bug.
- **A spy agency** → agency with `names=[…]`, `default_trigger="original_tag = <TAG>"`, upload a logo,
  then grow `upgrade_branches` via read-modify-write.
- **A custom puppet tier** → autonomy state with `is_puppet`, `min_freedom_level` (×1000!),
  `modifier={…}` dict, `rule` raw block, `ai_weights`. Move countries onto it from events/focuses via
  `set_autonomy` → **hoi4-wiring**.

## 3. Wiring out (→ hoi4-wiring / hoi4-build-scenario)
- **Focus → research**: a focus `completion_reward` grants `add_tech_bonus = { bonus=N uses=N
  category=<real category> }` (`construction`/`infrastructure` are NOT categories — use `industry`)
  or directly `set_technology = { <tech_id> = 1 }`.
- **Tech → hardware**: `enable_equipments` / `enable_subunits` on the tech are the unlock edges;
  `on_research_complete` fires an effect (e.g. an event) when researched.
- **OOB → country**: everything grouped under one `oob_file` (templates + deployments + air wings +
  fleets) lands in one starting-OOB file that the country's history must reference — the country/
  history side lives in **hoi4-build-scenario**. Deployment provinces and air-base states must exist:
  states are **edit-only** (seed from vanilla first), also **hoi4-build-scenario**.
- **Autonomy in play**: `set_autonomy = { target=<TAG> autonomy_state=<autonomy_id> }` from an event/
  focus/decision effect; `add_autonomy_ratio` moves the slider.
- **Designer ideas vs MIOs**: player-pickable designer companies = ideas (designer slot) →
  **hoi4-build-decisions-ideas**; trait-tree manufacturers = MIOs (this card).

## 4. Self-check after building (entity-level)
GET everything back and assert: tech `modifiers` uses `__modifier` (not a flat stat dict) and
`name=<tech_id>`; equipment variants carry `None` (absent), not `0`, for inherited stats; every
deployment's `division_template` name matches an existing template in the same `oob_file`; every
sub-unit token used in a template's `regiments` exists (vanilla or yours); wrapped lists (`mios`,
`agencies`, `autonomy_states`) actually contain your rows after unwrapping; doctrines emit under the
intended `entity_type`. Preview the sub-unit and OOB scripts (`/sub-units/preview/{id}`,
`/oob-units/preview`). Then run `POST /api/projects/{pid}/export/validate` +
`GET /api/lint/tree-validation/{pid}` (and `/special-projects/validate` if used) before the in-game
pass — `logs/error.log` is the final gate.

## 5. Common traps (distilled)
- 🔴 Tech `modifiers` as a flat `{stat: value}` dict → **silently dropped**; use
  `{"__modifier": "<raw flat script>"}` (see `field-reference/technologies.md`).
- 🔴 Sending `0` for an equipment variant stat you meant to inherit → a real zero override.
  `None`/omit = inherit.
- 🔴 MIO `traits` / agency `upgrade_branches`: no add endpoint — read-modify-write, never PUT a
  fresh list over the existing one.
- 🔴 Wrapped list GETs — `{"mios":[…]}`, `{"agencies":[…],"total":N}`, `{"autonomy_states":[…]}` —
  a naive `len()` reads 0 and you re-create duplicates.
- 🔴 `division_template` is a NAME ref within the same `oob_file` — a typo = the deployment silently
  refers to nothing; the OOB hierarchy in `/oob-units` is int-FK instead — don't mix the two idioms.
- 🔴 OOB scalars are strings (`"9601"`); ints are rejected. Empty string just omits the line.
- 🔴 `min_freedom_level` is freedom × 1000.
- 🔴 `armour_folder`, not `armor_folder`.
- Doctrine bonuses only live in `raw_extras`; switching `entity_type` silently changes what emits.
- DLC gates (§0.3): a MIO/agency/special-project/autonomy build is invisible without its DLC.
- States are edit-only — seed from vanilla before pointing deployments at provinces
  (→ **hoi4-build-scenario**).

## Cross-links
- Route table / transport / GET-then-POST protocol → **hoi4-build-api**.
- Field shapes → `field-reference/technologies.md` · `equipment.md` · `doctrines.md` ·
  `sub-units.md` · `division-templates.md` · `division-deployments.md` · `oob-units.md` · `mios.md` ·
  `special-projects.md` · `intelligence-agencies.md` · `autonomy-states.md` ·
  `_raw-script-fields.md` · `tokens.md`.
- Cross-entity wiring (focus→tech, set_autonomy, on_research_complete chains) → **hoi4-wiring**.
- Country history / `oob = "<stem>"` / states & territory → **hoi4-build-scenario**.
- Designer-company ideas → **hoi4-build-decisions-ideas**.
- Validate on the platform (`POST export/validate` + `GET lint/tree-validation`); the in-game
  `error.log` is the final gate → **hoi4-investigate**.
