---
name: hoi4-build-decisions-ideas
description: Use when filling the platform's **Decisions** workbench (decisions, categories, missions, targeted decisions) OR the **Ideas / national-spirits** workbench (spirits, designers, modifiers). The platform-form → in-game-output bridge + the cookbook + the field quirks a raw schema won't reveal (esp. decisions-are-global-by-default, category_id is an int FK, idea picture prefix-drop, removal_cost=-1 default, idea.modifier-is-dict-vs-decision.modifier-is-RAW, auto_attach_on_start). Invoke whenever creating/editing decisions, categories, or ideas via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Decisions + Ideas

A **build card** is the thin bridge between the platform form, the in-game output, and the player
experience. It does not re-list every field — **`field-reference/decisions.md`** and
**`field-reference/ideas.md`** already give the full field shape + meaning. This card carries only the
platform's per-field *emission map*, the cookbook, the wiring, and the validation discipline.

**Two entities, one card** — they wire tightly: decisions grant, swap, and remove national spirits.

Routes, nested `/decisions/categories`, icon/picture upload, and the auth pattern → **hoi4-build-api**.
The two headline traps here (decisions-are-global, idea-picture-prefix) also appear in build-api; this
card deepens them.

## 0. Before you fill the form
1. **Read `field-reference/decisions.md` + `field-reference/ideas.md`** for the full field list and
   meaning (esp. `allowed` "checks once at game start", `available` greys vs `visible` hides, idea
   `removal_cost`). Modifier stats + scopes → `field-reference/tokens.md`; which fields hold raw script →
   `field-reference/_raw-script-fields.md`.
2. **Validate EVERY token you write into a RAW field** — effects in `complete_effect` / `remove_effect` /
   idea `on_add`, triggers in `allowed` / `available` / `visible` / `target_root_trigger`, and every
   idea/decision `modifier` KEY. The platform lint checks a curated set of token-legality
   (`GET /api/lint/tree-validation/{pid}`) and `POST /api/projects/{pid}/export/validate` checks
   cross-refs + loc + assets. Neither proves full token validity — **your own game's `logs/error.log` is
   the final gate.** `add_ideas` / `swap_ideas` / `remove_ideas` / `add_timed_idea` / `has_idea` /
   `original_tag` are all COUNTRY-scope.

## 1A. DECISIONS — form → in-game output (idioms the field list won't spell out)

| Platform field | In-game output | Quirk |
|---|---|---|
| `decision_id` | `<decision_id> = {` nested inside its category block | mod-wide unique; a collision auto-suffixes `_1` + warns. loc keys `<id>` / `<id>_desc`. |
| `category_id` (**int FK**) | not emitted — selects the category block + the file bucket | 🔴 **It's the DB id of the category, NOT the HOI4 category string.** POST the category first, then use its returned `id`. |
| `scope_kind` / `country_tag` / `shared_country_tags` | **nothing in-game** — they only organize the export bucket | 🔴🔴 **THE headline trap:** these do NOT restrict in-game visibility. A "country-specific" decision with a blank `allowed` shows for EVERY country. |
| `allowed` (RAW) | `allowed = { … }` verbatim — **the only static country gate** (checked once at game start) | 🔴 NOT synthesized from `scope_kind`. To restrict: `allowed = "original_tag = <TAG>"` (+ category `visible = "original_tag = <TAG>"`). |
| `available` (RAW) | `available = { … }` | False → decision stays VISIBLE but **greyed**. Use this to show-but-disable. |
| `visible` (RAW) | `visible = { … }` | False → **hidden** from the screen. |
| `complete_effect` (RAW) | `complete_effect = { … }` | 🟢 If `effect_tooltip_locs` has text, export injects `custom_effect_tooltip = <id>_et_tt` INSIDE it + emits the loc — the readable-tooltip fix for var/flag rewards that otherwise show an empty effect box. |
| `target_root_trigger` (RAW) | `target_root_trigger = { … }` — its PRESENCE makes the decision TARGETED | 🔴 When false it **HIDES the whole decision** (does not grey it). To show-but-disable a targeted decision use `available`. In a targeted decision ROOT = taker, FROM = current target. |
| `targets` (list) / `target_array` / `target_trigger` / `state_target` | `targets = { TAG TAG }` etc. | Dedicated columns. Get the `set_autonomy` / `puppet` direction right: `target = FROM` in ROOT scope. |
| `cost` / `days_remove` / `days_re_enable` / `modifier` / `ai_will_do` / `priority` | emit-if-truthy | `days_remove` = how long the `modifier` runs; `days_re_enable` = cooldown before re-take. **decision.modifier is RAW text** (contrast idea.modifier = dict). There is no `days` field — it's `days_remove`. |
| mission flow: `activation` / `timeout_effect` / `days_mission_timeout` / `selectable_mission` / `is_good` | turn a decision into a MISSION | mission = `days_mission_timeout` + `activation` (appears when true) + `available` (completion) + `timeout_effect` (penalty). `is_good` colors the bar. |
| category `category_id` (str) | `<category_id> = {` block | **This** string is the real HOI4 token — the int FK above resolves to it. |
| category `allowed` / `visible` (RAW) | verbatim | To make a category country-specific set BOTH the category `visible = "original_tag = X"` AND each decision's `allowed = "original_tag = X"`. |
| category `visibility` (enum visible/solo/hidden) | platform-only filter | `hidden` → the category AND its decisions' SCRIPTS are not emitted (loc still emits to avoid dangling keys). A "hidden" category's decisions silently never appear in-game. |

## 1B. IDEAS / NATIONAL SPIRITS — form → in-game output

| Platform field | In-game output | Quirk |
|---|---|---|
| `idea_id` + `idea_type` (default `country`) | `ideas = { <idea_type> = { <idea_id> = { … } } }` | `country` = a national spirit; designer types auto-get `designer = yes`; `hidden_ideas` has no picture slot. loc `<id>` / `<id>_desc`. |
| `picture` | export emits the resolved sprite **with `GFX_idea_` stripped** | 🔴 value `foo` → the vanilla sprite `GFX_idea_foo`. **UNSET → no `picture` line → "?" placeholder** in the political screen (the modifier still applies). 🔴🔴 **Even when SET, export only emits a picture whose sprite name is in the platform's known sprite registry** — a name it doesn't recognize (some of your own tag-prefixed custom sprite names, plus certain DLC sprites such as `BEL_rexist_legion` / `PER_iranian_oil_company`) is silently dropped → "?" in-game even though the platform export passed green. Registry-known vanilla names emit fine (`generic_*`, `standard_oil_california`, base-game `ARG_/BOL_/ETH_/HUN_*`, …). Fix for an unrecognized sprite: upload your own via the idea's `upload-picture`. The tell is a "?" in your own game. |
| `name` (internal, ≠ `name_en/zh`) | 🔴🔴 export emits it UNQUOTED as `name = <value>`, and it DEFAULTS to `"New Idea"` (a string **with a space**) | HOI4 parses `name = New`, then `Idea` is an `Unexpected token` → the parser DESYNCS and drops the rest of that idea block (including `picture`) → the spirit's icon shows "?". This hits EVERY idea built via API that doesn't set `name`. **Fix: PUT `name` = the `idea_id`** (a space-free token — the platform then SKIPS emitting the `name` line entirely and HOI4 falls back to the `idea_id` loc key = correct display). |
| `modifier` (**dict**) | `modifier = { k = v … }` | 🔴 **idea.modifier is a DICT** (k:v), not raw text. `__`-prefixed keys are platform-internal (`__ai_will_do` is pulled out to a separate `ai_will_do`). Validate keys vs `field-reference/tokens.md`. |
| `removal_cost` (default **-1**) | `removal_cost = <n>` (emit when ≠ 0) | 🔴 **Default -1 = CANNOT be removed manually** (a permanent spirit). 0 = removable (no line emitted); positive = PP cost to remove. |
| `allowed` / `available` / `visible` (RAW) | each wrapped | `allowed` gates which countries can *select* it, but manual `add_ideas` BYPASSES `allowed`. Most authored spirits leave `allowed` blank and attach via `add_ideas` / on_startup. |
| `on_add` / `on_remove` / `do_effect` / `cancel` / `allowed_civil_war` (RAW) | each wrapped | `on_add` can itself `add_ideas` a second spirit (chaining). RAW — validate tokens. |
| `research_bonus` (dict) / `designer_traits` (list) / `equipment_bonus` / `targeted_modifier` / `rule` / `level` / `ledger` | designer / advanced fields | `research_bonus` category must be a real tech category. `targeted_modifier` = list of `{tag, modifier}` → one block each. (NOTE: `research_bonus` IS valid here — an idea-definition block — unlike inside a focus `completion_reward`.) |
| `auto_attach_on_start` (default **true**) | controls the on_startup auto-attach | 🔴 Every `idea_type="country"` idea is attached to its country at on_startup **only if `auto_attach_on_start=True`**. Since `add_ideas` bypasses `allowed`, `allowed = { always = no }` alone does NOT keep a spirit off at start — set `auto_attach_on_start=false` on any conditional / endgame spirit so it's excluded from the auto-attach, then `add_ideas` it in the granting focus/event. Do NOT dodge the filter by pointing `country_tag` at a dummy tag — a non-primary `country_tag` makes export emit a phantom country block that can corrupt the primary country's startup hooks. |

## 2. Want experience X → fill fields Y (cookbook)
- **PP-spending decision restricted to ONE country** → decision `cost=N`, `complete_effect="<raw>"`, `allowed="original_tag = <TAG>"`; category `visible="original_tag = <TAG>"`. (`scope_kind` alone does NOT restrict.)
- **Decision greyed until ready** → `available="<raw trigger>"` (NOT `target_root_trigger`, which hides it). Hide completely → `visible`.
- **Timed mission** → `days_mission_timeout=N`, `activation`, `available` (completion), `complete_effect` (reward), `timeout_effect` (penalty), `is_good=true`.
- **Targeted decision against a country list** → `target_root_trigger="<daily gate>"`, `targets=["A","B"]` (or `target_array`), `target_trigger`; `complete_effect` addresses `FROM`.
- **Decision whose only reward is a var/flag, shown readable** → `complete_effect="add_to_variable…"` + `effect_tooltip_locs={"en":…,"zh":…}` → first-class `<id>_et_tt` injection (no empty effect box).
- **Permanent national spirit with a modifier** → `idea_type="country"`, `modifier={…dict…}`, `name` + `desc` in both languages, `picture="<vanilla-sprite-minus-GFX_idea_>"`, `removal_cost=-1` (default, non-removable). Also PUT `name = <idea_id>` to dodge the `"New Idea"` desync. With `auto_attach_on_start=true` (default) it attaches at game start.
- **Endgame / conditional spirit that must NOT be on at start** → `auto_attach_on_start=false`, then `add_ideas` it in the granting focus/event. (`allowed={always=no}` alone won't hold — `add_ideas` bypasses `allowed`.)
- **Spirit that upgrades on a focus/event** → two country ideas (tier1 / tier2); the effect does `swap_ideas = { remove_idea = tier1 add_idea = tier2 }`. Temporary buff → `add_timed_idea`.

## 3. Wiring out (→ hoi4-wiring)
- Decision `complete_effect` → `add_ideas` / `swap_ideas` / `remove_ideas` grants or upgrades a spirit (the canonical decisions↔ideas link), or `country_event = { id }` fires a story event, or `set_cosmetic_tag` renames the country.
- focus/event → decision: set a `country_flag` that the decision's `available` / `visible` reads (decisions have no "unlock" field beyond their own gates).
- `add_ideas` MUST be inside an effect block (on_startup / `complete_effect` / focus reward / event) — never bare. Full scope-passing chains → **hoi4-wiring**.

## 4. Self-check after building (entity-level)
GET each entity back and assert: every decision's `category_id` points at a real category id; country-specific decisions have `allowed=original_tag=X` (+ category `visible`); no category is accidentally `visibility="hidden"`; every spirit has `name` set to its `idea_id` (not the `"New Idea"` default) and a registry-known `picture` (or you accept the "?"); `removal_cost` is intentional; every RAW token + modifier key was validated (§0). Then `POST .../export/validate` + `GET /api/lint/tree-validation/{pid}`, download the ZIP, load it in your own game, and read `logs/error.log`.

## 5. Common traps (distilled)
- 🔴 Decisions are GLOBAL by default — `scope_kind` / `country_tag` only organize the export file; restrict with `allowed=original_tag=X` (+ category `visible`).
- 🔴 `category_id` is the **int** DB FK, not the HOI4 category string.
- 🔴 `target_root_trigger` HIDES when false (use `available` to grey).
- 🔴 idea `picture` drops the `GFX_idea_` prefix; UNSET → "?" placeholder; a sprite the platform doesn't recognize is silently dropped even when SET.
- 🔴 Leave idea `name` unset → export writes `name = New Idea` → parser desync → "?" icon. Always PUT `name = <idea_id>`.
- 🔴 `removal_cost` default -1 = non-removable.
- 🔴 idea.modifier = **dict** but decision.modifier = **RAW text**.
- 🔴 `auto_attach_on_start=false` (not `allowed=always=no`) is how you keep a country spirit dormant until granted.
- category `visibility="hidden"` silently suppresses its decisions' scripts.
- `add_ideas` must be inside an effect block.

## Cross-links
- Routes, payload shapes, auth (`Authorization: Bearer` from `HOI4_PLATFORM_TOKEN`) → **hoi4-build-api**.
- Cross-entity wiring (a decision fires an event, a flag a later focus reads, spirit succession) → **hoi4-wiring**.
- Root-cause an in-game bug from `logs/error.log` → **hoi4-investigate**.
