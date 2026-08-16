---
name: hoi4-build-focus
description: Use when filling the HOI4 mod platform's **Focus Trees** workbench (focus nodes: prerequisites, mutually-exclusive branches, completion_reward effects, layout, continuous/cancelable focuses). The platform-form → in-game → player-experience cookbook plus the focus quirks a GET or the field table won't reveal (prerequisites = list[list], the raw completion_reward token traps, effect_tooltip_locs, the malformed-effect cascade drop, and the load_focus_tree overlap). Invoke whenever creating or editing focus nodes via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Focus Trees

The **field shapes** for `/focus-trees` and its nested `/focus-trees/{tree_id}/nodes` live in
`field-reference/focus.md` (every field + type), the raw-script fields in
`field-reference/_raw-script-fields.md`, and the token vocabulary in `field-reference/tokens.md`. Read
those for *what each field is*. This card is the layer on top: **what a focus MEANS in the game, the
recipes for the experience you want, and the quirks a GET can't show you.** Route table /
GET-to-learn-the-shape / auth → **hoi4-build-api**. Cross-entity wiring (focus → event / decision /
advisor) → **hoi4-wiring**.

## 0. Before you fill the form — validate on the platform
1. Read `field-reference/focus.md` (field shapes) and `field-reference/tokens.md` (what's legal in each
   raw field).
2. Every token you put in a RAW field (`completion_reward` / `select_effect` / `available` / `bypass` /
   `cancel`) is passed through verbatim — the platform checks only a curated subset of token legality.
   Run both before the in-game pass:
   - `POST /api/projects/{pid}/export/validate` (cross-refs closed, loc complete in both languages,
     assets shipped)
   - `GET /api/lint/tree-validation/{pid}` (token legality + structure)
   Then load the exported ZIP in your own game and read `logs/error.log` — the final gate for tokens the
   lint can't know about (an `effect.cpp: Invalid effect` line names the offender).
3. Two traps that pass a shape check but fail in-game (see §5): `research_bonus` is NOT a valid focus
   effect, and `add_tech_bonus` category must be a real tech category.

## 1. What a focus field MEANS (the idioms a GET won't reveal)
- **`focus_id` is project-wide unique across ALL trees.** A collision does NOT 422 — the platform
  silently auto-suffixes `<id>_1` and returns a `warnings: […]` line in the POST response. Re-running a
  tree build stacks a duplicate `_1` set on the same x/y (an invisible overlap). **Read the POST
  `warnings` every time**; if you see `_1` duplicates, DELETE the orphan set.
- **`cost` is completion time in weeks** (default 10). A `continuous` focus MUST be `cost = 0`.
  Progressive tiers pace a chain: early/process focuses cheap (~5), stage focuses ~10, capstones 10-15 —
  redistribute the same total so the middle gives less and the endpoint gives more.
- **`x`/`y` is a grid position; the icon is a 2×2 square centred on it.** Two nodes at the same (x,y) in
  one tree → the game **crashes on load**. Keep same-row Δx ≥ 2, same-col Δy ≥ 1. The tree is
  **left-anchored**, and TWO things occlude the left edge, both anchored at tree origin x=0: (a) the small
  flag ornament (~2-3 columns → clear it with min-x ≈ 4), and (b) the **vanilla continuous-focus panel**
  (~770px ≈ 8-9 grid columns wide) that appears on any vanilla-based tree — to clear THAT, shift the whole
  tree so min-x ≈ 12. min-x ≈ 4 only clears the ornament; a lane sitting at x 4-13 will be half-hidden
  under the continuous-focus panel. With `relative_position_id` set, x/y become OFFSETS from that node.
- **`relative_position_id` anchors must be created BEFORE the node that points at them** — the export
  emits in insertion order, so build parents first or you get a "relative focus must be scripted before
  this" error.
- **`prerequisites` = `list[list[str]]`: OUTER = AND, INNER = OR.** `[["a"]]` = needs a; `[["a","b"]]` =
  needs a OR b; `[["a"],["b"]]` = needs a AND b. Each inner group emits one `prerequisite = { focus = … }`
  line.
- **`mutually_exclusive` must be SYMMETRIC** — list every sibling on each branch-entry node. If A lists B
  but B doesn't list A, the game errors ("has mutual exclusivity with X but the other focus does not").
  This is where a double-POST `_1` duplicate most often surfaces.
- **`completion_reward` holds RAW effect script and is ALWAYS emitted** (even when empty, so an
  effect-tooltip line can inject). Token validity is NOT checked at export. 🔴 **A malformed effect here
  desyncs the PDX parser and silently DROPS EVERY focus after it in the file** — whole chains vanish
  in-game while the export stays green (`error.log` shows a run of `Unexpected token: focus …`). The
  classic trap is VALUE SHAPE, not token name: `set_country_leader_ideology` takes a **scalar**, not a
  block — write `set_country_leader_ideology = fascism_ideology`, never
  `= { ideology = fascism_ideology }` (the block form parses as an invalid effect and cascades). Other
  scalar-taking effects to write bare: `set_cosmetic_tag = X`, `retire_character = X`,
  `promote_character = X`, `load_focus_tree = X`, `add_to_faction = X`. Self-check after any chain build: a
  run of `Unexpected token: focus` in `error.log` pinpoints the first malformed focus.
- **`effect_tooltip_locs` is a first-class focus field** (dict `{lang: text}`). Variable/flag rewards
  (`add_to_variable`, `set_country_flag`) have NO auto-tooltip, so a focus whose only reward is a flag/var
  change shows an empty green box. Fill `effect_tooltip_locs` and the export injects
  `custom_effect_tooltip = <id>_et_tt` inside `completion_reward` and emits the loc — no raw files needed.
  Both the script side and the loc side gate on non-empty, so keep the languages in sync.
- **`available` greys the focus; `select_effect` fires when it STARTS; `bypass` auto-completes;
  `cancel` auto-fails.** All hold raw trigger/effect text (→ `field-reference/_raw-script-fields.md`).
- **`ai_will_do` defaults to `factor = 1`.** Set `factor = 0` for player-only choices so the AI won't
  auto-pick them.
- **`allow_branch` is a structured AST, not a raw string** — it hides a whole branch when false. There is
  no plain free-text `allow_branch` field; use the structured `allow_branch_ast`.
- **`continuous` / `cancelable` and the continuous-focus `modifier = {}` are NOT first-class node
  fields** — they ride via the node's `raw_extras` passthrough. A continuous focus = `continuous = yes`
  + `cost = 0` + a `modifier = { … }` (its passive bonus goes in that modifier, NOT `completion_reward`).
  But `cancel_if_invalid` / `continue_if_invalid` / `available_if_capitulated` ARE first-class boolean
  fields (defaults yes / no / no) — set them on the column; a `raw_extras` copy of them is silently
  ignored.
- **`icon` falls back to `GFX_goal_unknown`** (generic but working, no missing-texture) when a custom
  sprite isn't shipped. Reuse a vanilla `GFX_goal_*` or upload your own via
  `POST .../nodes/{id}/upload-icon`.
- **Both loc languages or nothing.** `name_en`/`name_zh` → key `<id>`; `desc_en`/`desc_zh` → `<id>_desc`.
  Fill BOTH or the missing locale shows the raw token; `export/validate` flags the asymmetry.
- **The tree's `country_tag` is who sees it, but the primary country does NOT auto-load its own tree by
  tree-scoring alone.** File several trees under one tag and they OVERLAP in-game. Bind each tree to its
  real owner and drive the explicit `load_focus_tree` through wiring (§4) — do NOT "fix" overlap by
  spreading x-positions.

## 2. Want experience X → fill fields Y (cookbook)
- **Linear progression branch (start → mid → capstone)** → 3 nodes: root has empty `prerequisites` +
  absolute x/y (min-x ≈ 4, or ≈ 12 on a continuous-focus tree, per §1); each child
  `relative_position_id = <parent>` + `x = 0`, `y = 1`. Cost per progressive tier (5 / 10 / 10-15),
  redistributing one total. Keep any single chain ≤ 3 deep — branch and merge instead of one long
  vertical line.
- **Two mutually-exclusive choices** → both branch-entry nodes share `prerequisites = [[parent]]`; node A
  `mutually_exclusive = ["B"]`, node B `mutually_exclusive = ["A"]` (🔴 symmetric); Δx ≥ 2; optionally
  `ai_will_do = "factor = 0"`.
- **Research-boost reward** →
  `completion_reward = "add_tech_bonus = { bonus = 0.5 uses = 1 category = industry }"` — 🔴 NOT
  `research_bonus`, and a real category (§5).
- **A variable/flag reward shown as a readable green line** →
  `completion_reward = "add_to_variable = { var = TAG_x value = 5 }\nset_country_flag = done"` +
  `effect_tooltip_locs = {"en":"§GGain 5 X§!","zh":"§G获得5点X§!"}`.
- **Continuous focus (passive bonus)** → `cost = 0`, a `search_filters` tag (e.g. `FOCUS_FILTER_ARMY_XP`),
  and `raw_extras` carrying `continuous = yes` + `modifier = { army_experience_gain_factor = 0.05 }` (NOT
  `completion_reward`).
- **Cancelable mobilization** → `cost = 30`, `cancel = "add_stability = -0.05"`,
  `cancel_if_invalid = true`, `ai_will_do = "factor = 0"`.
- **Condition-gated focus (greyed but visible)** →
  `available = "has_completed_focus = X\ndate > 1937.1.1"`. To HIDE the whole branch instead →
  `allow_branch_ast`.

## 3. Laying out a big multi-path tree cleanly
For N ideology/route branches, lay each branch out as its OWN vertical lane, side by side (like vanilla
Mexico), NOT interleaved:
1. **Confirm the branches are separable** — GET the nodes and check each one's prereqs stay WITHIN its
   branch (a shared opening + per-branch selectors with zero cross-lane prereq edges = perfectly
   laneable).
2. **`y = tier`** = longest-prereq-path depth (children always below parents).
3. **`x` = per-lane tidy tree:** DFS post-order, leaves get consecutive columns (step 2), each parent
   centred over its children; then offset each lane into its own x-band (gap ≈ 3 between lanes).
4. **Shared opening spine** centred at top, fanning out to each lane's selector.
5. **Shift so min-x ≈ 12** — the leftmost lane must clear BOTH left occluders, especially the
   continuous-focus panel (§1).

**Preview WITHOUT the game:** GET the nodes and render them as boxes at (x, −y) with prereq lines coloured
per branch (matplotlib is enough) → a PNG that reads like the in-game tree, so you tune the layout and get
sign-off before PUTting 100+ positions. Positions are pure-visual (logic untouched) — back up the old x/y
first, PUT the new ones, then GET the nodes back and confirm each x/y round-tripped.

## 4. Wiring out (→ hoi4-wiring)
- **focus → event:** `completion_reward = "country_event = { id = ns.N days = N }"` (the event must exist
  first — a typo'd ref is silently dropped; `export/validate` catches it).
- **focus → advisor unlock:** the *character's* `advisor_available` holds `has_completed_focus = <id>` →
  **hoi4-build-characters**.
- **Make the primary country actually SHOW the tree:** bind the tree's `country_tag` to its real owner,
  and drive the explicit `load_focus_tree` through the history-files workbench → **hoi4-wiring**. The
  primary does NOT get it for free; without it, trees filed under the same tag overlap.
- **Flags/vars/scopes passed across entities** (THIS/ROOT/FROM/PREV) → **hoi4-wiring**.

## 5. Self-check + common traps
**Self-check (GET your nodes back and assert):** no `warnings` in any POST response (no silent `_1` dup);
no two nodes share (x,y) in one tree; every `mutually_exclusive` is reciprocal; every `prerequisites` /
`relative_position_id` target exists in the same tree; min-x ≈ 4 (or ≈ 12 on a continuous-focus tree);
both `name_en` + `name_zh` filled; every `completion_reward` token validated (§0). Then `export/validate`
+ `lint/tree-validation` + your game's `error.log` are the final gates.

**Common traps (distilled):**
- 🔴 Double-POST → silent `<id>_1` stacked dup (check POST `warnings`).
- 🔴 Same (x,y) in one tree → load crash.
- 🔴 Asymmetric `mutually_exclusive` → mutual-exclusivity error.
- 🔴 Malformed `completion_reward` (esp. a scalar effect written as a block) → every following focus
  silently dropped in-game while the export stays green.
- 🔴 `research_bonus` as a focus effect, or `add_tech_bonus category = construction|infrastructure` →
  passes a shape check, fails at `error.log` (use `add_tech_bonus` with `category = industry`).
- 🔴 Primary country missing its `load_focus_tree` → overlapping trees.
- Left-anchor: min-x ≈ 0 hides behind the left occluders — the flag ornament needs min-x ≈ 4, the
  continuous-focus panel needs min-x ≈ 12.
- Omitting one of `name_en`/`name_zh` → raw token shows in the missing locale.
- Flag/var reward with no `effect_tooltip_locs` → empty effect box.
- Continuous focus without `cost = 0` → broken.
- `allow_branch` is an AST, not a raw string.

## Cross-links
- Route table + auth (Bearer token from `HOI4_PLATFORM_TOKEN`, base URL from `HOI4_PLATFORM_URL`) →
  **hoi4-build-api**.
- Cross-entity wiring / scope-passing → **hoi4-wiring**.
- Field shapes → `field-reference/focus.md`; raw-script fields → `field-reference/_raw-script-fields.md`;
  token vocabulary → `field-reference/tokens.md`.
