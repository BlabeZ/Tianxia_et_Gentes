---
name: hoi4-build-events
description: Use when filling the HOI4 mod platform's **Events** workbench (country_event / news_event / state_event, namespaces, options, immediate/trigger/after, auto-fire via on_actions) — or building a **super event** (fullscreen ceremonial event with background art + music + staged text, its own `/super-events` workbench). The platform-form → in-game event bridge + the cookbook + the field quirks a GET won't reveal (esp. is_triggered_only↔MTTH exclusivity, per-option effect_tooltip, option loc-key collisions, and that scope_kind does NOT gate visibility). Invoke whenever creating/editing events or super-events via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Events

> **A "build card" = the thin bridge between the platform form, the HOI4 output, and the player
> experience.** It does NOT re-teach the full field table — `field-reference/events.md` already maps every
> field to its HOI4 token, and `field-reference/tokens.md` / `field-reference/_raw-script-fields.md` cover
> token legality and which fields hold raw script. This card carries only the per-field emission map, the
> cookbook, the wiring, and the validation discipline.
>
> Route table / nested `/events/namespaces` / picture upload → **hoi4-build-api**. Cross-entity wiring
> (focus→event, event→on_actions, succession, THIS/ROOT/FROM scope-passing) → **hoi4-wiring**.

## 0. Before you fill the form — two validation sources
1. **Read `field-reference/events.md`** for the field shapes (event types, the `<namespace>.<int>` id
   rule, conditional-title syntax, the option-dict keys).
2. **Validate EVERY token** you put in any RAW field (`trigger` / `mean_time_to_happen` / `immediate` /
   `after`, plus each option's `effects` / `trigger` / `hidden_effects`). Token legality lives in
   `field-reference/tokens.md`; the platform checks a curated set for you at export
   (`POST /api/projects/{pid}/export/validate` + `GET /api/lint/tree-validation/{pid}`); the in-game
   `logs/error.log` is the final gate for anything the lint can't know. Remember the scope: a
   `country_event` runs in COUNTRY scope, a `state_event` in STATE — a token legal in one is illegal in
   the other.

## 1. Platform form → HOI4 output (the mapping the GET won't explain)

| Platform field | HOI4 output | Quirk |
|---|---|---|
| namespace + `namespace_id` | `add_namespace = <ns>` emitted once for the namespace | Namespace must exist FIRST (create it via the nested namespaces route — see **hoi4-build-api**). `event_id` MUST be `<ns>.<int>`. 🔴 **The namespace string must be MOD-UNIQUE — it must NOT match a vanilla or base-mod namespace.** HOI4 hashes the namespace name into a numeric id base; a collision makes your `<ns>.N` share the numeric id of the base game's `<ns>.N`, which the game logs as "Already exists in game" — a crash risk. **Fix: prefix-qualify** with a short mod-specific tag (e.g. `mymod_ger`, not a bare `germany`). |
| `country_tag` / `scope_kind` / `shared_country_tags` | **nothing in-game** — events emit NO `allowed` block | 🔴 **TRAP: these do NOT scope visibility.** They only organize which export file the event lands in. To scope an event, write the limit into its `trigger` / option `trigger`, or only fire it from the right country. |
| `event_id` + `event_number` | `id = <event_id>` (verbatim) | `event_number` is the sort key within the file, not re-derived into the id. A colliding id auto-suffixes and is flagged. |
| `event_type` | `country_event` / `news_event` / `state_event` `= {` | All three real. `news_event` uses `major = yes` for world display. |
| `title_en/zh`, `desc_en/zh` (or `display_name_locs` / `description_locs`) | `title = <id>.t` / `desc = <id>.d` + loc lines in both languages | **Derived keys — you fill the text, never type `.t`/`.d`.** Symmetric emit (fill any one language → both are emitted, with fallback). A plain `title` STRING emits verbatim (the hidden-helper idiom). A `title` LIST of `{text, trigger}` → a conditional-title block. |
| `options[]` (`list[dict]`: `name`, `name_en/zh`, `trigger`, `effects`, `hidden_effects`, `ai_chance`, `effect_tooltip_en/zh`) | `option = { name=<key> trigger={} <effects RAW> hidden_effect={} ai_chance={} }` per option | 🔴 `name` = the loc **KEY** (button text = `name_en/zh`). Blank `name` → auto `<id>.<a\|b\|c…>`. `effects` / `trigger` / `hidden_effects` are RAW inner script. `ai_chance` unset → forced `{ base = 100 }` (deterministic — `base` ≠ `factor`, modifier `add` ≠ `factor`). 🔴 **Option key must AVOID `.t`/`.d`** — a 4th option keyed `<id>.d` collides with the auto desc key (use `<id>.optd`). |
| option `effect_tooltip_en/zh` (inside the option dict) | injects `custom_effect_tooltip = <opt_key>_tt` + loc both languages | 🟢 **First-class — but PER-OPTION only** (there is no event-level `effect_tooltip` field). This is how a variable/flag-change option gets a colored (`§G…§!`) tooltip instead of an empty box. |
| `is_triggered_only` (schema default **True**) | `is_triggered_only = yes` | 🔴 **Mutually exclusive with `mean_time_to_happen`** — both filled → the event won't fire. For a self-firing MTTH event you MUST explicitly send `is_triggered_only=False`. |
| `mean_time_to_happen` (RAW) | `mean_time_to_happen = { … }` | RAW inner. Modifier order: `factor` FIRST then the condition (reversed = no-op). |
| `trigger` / `immediate` / `after` (RAW) | each wrapped | `immediate` = pre-popup setup (`save_event_target_as`, wrap in `hidden_effect`); `after` = on-close cleanup. Emission order: flags → trigger → MTTH → immediate → options → after. |
| `hidden` / `fire_only_once` / `major` / `timeout_days` | emit-if-truthy | `hidden=True` + `is_triggered_only=True` = a hidden helper / heartbeat. `major = yes` = news world display. |
| `auto_fire_on_startup` / `auto_fire_after_days` / `on_action_attach` | NOT in the event script — the platform generates a separate on_actions entry | The engine-legal way to self-fire WITHOUT a focus/decision caller. `auto_fire_after_days=N` alone is sufficient for a dated auto-fire (defaults to the `on_startup` hook, fired N days in via `country_event = { id=X days=N }`); `auto_fire_on_startup=True` forces the `on_startup` hook (days=0 → fires at startup); `on_action_attach` (if set) wins and routes into that named hook (30+ hook enum) with a per-country `if = { limit = { tag = … } }` guard. An event with NONE of these stays off on_actions. → **hoi4-wiring**. |
| `picture` | `picture = <sprite>` — **image-gated on export** | A custom picture name with no actual upload is DROPPED (falls back to the default frame). Use a vanilla `GFX_*_event_*` sprite or upload via `POST /events/{id}/upload-picture`. |
| `raw_extras` (Update/Response only) | re-emitted `key = value` / `{}` | Import-preserved mod-custom keys. NOT on create (preserve-on-import, not author-on-create). |

## 2. Want experience X → fill fields Y (cookbook)
- **Player-facing decision event** → `event_type=country_event`, `is_triggered_only=True`, `hidden=False`,
  `fire_only_once=True`, `title_en/zh` + `desc_en/zh`, `options=[{name:"<id>.a", name_en/zh,
  effects:"<RAW>", ai_chance:{base:N}}]`. Fire it from a focus / option / on_action via
  `country_event = { id=<id> }`.
- **Hidden helper / heartbeat (no UI)** → `hidden=True`, `is_triggered_only=True`, no title/desc, one
  option carrying the `effects`. Loop it: the option's `effects` does `country_event = { id=<self> days=N }`.
- **Self-firing dated / random event** → `is_triggered_only=False` (clear it!), `trigger="<RAW>"`,
  `mean_time_to_happen="days = 30  modifier = { factor = 0.5 <cond> }"`, `fire_only_once=True`.
- **Option with a colored, visible effect line (var/flag reward)** → in the option dict set
  `effect_tooltip_en` + `effect_tooltip_zh` (first-class per-option; export injects
  `custom_effect_tooltip = <opt_key>_tt`).
- **Conditional title / desc** → pass `title` / `description` as a LIST of `{text, trigger}` dicts (ship the
  text via the loc fields).
- **Leader succession** → option `effects = "kill_country_leader = yes\ncreate_country_leader = { name=…
  ideology=… }"`. Keep ONE `country_leader` char per ideology — do NOT pre-create a duplicate →
  **hoi4-build-characters**.

## 3. Super-events (fullscreen ceremonial layer)

A **super-event** is a fullscreen ceremonial moment — big background art + music + staged
title/quote/button — the dramatic-beat weapon (war declarations, capitulations, era transitions).
It is a **separate workbench** (`POST/PUT/DELETE /api/projects/{pid}/super-events`), NOT a flag on
a normal event. Field shapes live in `field-reference/super-events.md`; this section carries only
what the field table won't tell you.

**How it differs from a normal event.** You do NOT author a namespace, an event id, or a popup
window. You supply the staged text (`title` / `quote` / `btn` / `desc`, en+zh), an optional
`song_token`, an optional background upload, and an `options` list. At export the platform
generates the whole delivery stack for you: a hidden driver `country_event` (auto-id
`<tag>_se.<number>`, e.g. `ger_se.1`, in an auto namespace `<tag>_se`), the fullscreen
scripted-GUI overlay, the localisation routers, and neutral placeholder frame art so the layer
renders out of the box (no missing-texture crash). Your uploaded background replaces the
placeholder picture box; everything else is regenerated every export.

**How it fires — exactly like a normal event, via the derived id:**
- From any effect: `country_event = { id = <tag>_se.<number> }` in a focus `completion_reward`,
  an event option's `effects`, a decision effect, or another super-event option's `effect`
  (SE → SE chains work).
- Or self-fire: `auto_fire_after_days=N` alone schedules at game start and fires N days in;
  `auto_fire_on_startup=True` is an OR'd enable switch (fires day 0 when `N=0`) — you do NOT need
  both for a delayed fire.
- 🔴 **Dormant-drop trap:** a super-event with no auto-fire AND no `country_event` reference to
  its `<tag>_se.<number>` id anywhere (events / decisions / focus rewards / other SE options) can
  never fire, so the export DROPS it entirely (surfaced in the export skip log, easy to miss).
  Wire it or set auto-fire before expecting it in the zip.

**Form highlights (full table → `field-reference/super-events.md`):**
- `number` = 4-digit id, unique per country per project (clash = 409). The in-script id derives
  from it: `<tag lowercase>_se.<number>`.
- `options` empty → a single "Continue" button (fine for pure ceremony). Each option =
  `{name_en, name_zh, effect, ai_chance}`; `effect` is RAW script run on click — validate its
  tokens like any RAW field (§0).
- `btn_en/zh`: always set it — empty falls back to an ugly literal.
- **Picture is upload-only**: `POST /super-events/{se_id}/upload-picture`. A vanilla sprite name
  in `picture_path` is IGNORED (unlike normal-event `picture`) — no upload = gray placeholder box.
- `song_token` plays when the super-event opens.

**Cookbook — war-declaration ceremony fired from a focus:**
1. `POST /super-events` → `{number: 1, country_tag: "GER", title_en/zh, quote_en/zh, btn_en/zh,
   desc_en/zh, song_token: "<track>", options: [{name_en: "To war!", name_zh: "…",
   effect: "declare_war_on = { target = POL type = annex_everything }", ai_chance: 1}]}`.
2. Upload the fullscreen background: `POST /super-events/{se_id}/upload-picture`.
3. In the focus, `completion_reward = "country_event = { id = ger_se.1 }"` — this reference is
   also what keeps the SE out of the dormant-drop filter.
4. Self-check: **there is no single-GET** (405) — read back via the list GET, and note it returns
   a **WRAPPED object** `{"super_events":[…]}` — unwrap the key or a naive `len()` reads 0
   (false "empty"). Then platform validate + in-game check as in §5.

## 4. Wiring out (→ hoi4-wiring)
- focus `completion_reward` → `country_event = { id = ns.N }` fires this event (event + namespace must exist
  first; a typo'd ref is silently dropped — run platform validate to catch it before the game does).
- option `effects` chains out: `set_country_flag` / `set_variable` (read later by a focus/decision
  `available`), `set_country_leader_ideology`, `add_ideas`, `load_focus_tree`, `country_event` (chain).
  All RAW — validate scope.
- `auto_fire_*` / `on_action_attach` wire the event into the generated on_actions. Full chains + the scope
  footguns → **hoi4-wiring**.
- **Submod base-mod refs:** for a submod project, base-mod entity refs autocomplete once the base mod is
  indexed; at export the base-mod **idea / character / focus / decision** ids are gated (undefined →
  flagged), **country_tag** is picker-only (not gated), and **ideology / state** ids feed a
  false-positive-suppressing scan. The per-event editor lint is NOT base-mod-aware, so raw effect/trigger
  token validity is still author-verified via platform validate + your in-game `error.log`. → **hoi4-submod**.

## 5. Self-check after building (entity-level)
GET your events back and assert: namespace registered; never `is_triggered_only` AND `mean_time_to_happen`
both set; no option key is `.t`/`.d`; both languages of title/desc filled; every RAW token validated (§0).
Then run `POST /api/projects/{pid}/export/validate` — no cross-refs dropped, loc complete in both languages,
picture assets shipped — before the in-game pass.

## 6. Common traps (distilled)
- 🔴 `is_triggered_only` + `mean_time_to_happen` both set → event never fires (schema default
  `is_triggered_only=True` — send `False` for MTTH events).
- 🔴 option key `<id>.d` / `.t` → loc collision (use `<id>.optd`).
- 🔴 `scope_kind` / `country_tag` do NOT gate visibility — they only organize the export file (scope via
  `trigger`).
- 🔴 `effect_tooltip` is per-OPTION; there is no event-level field.
- picture dropped if there is no real upload.
- `ai_chance` unset → forced `base=100` (not "AI ignores it").
- omit one title/desc language → the export flags a loc-symmetry warning.
- typo'd `country_event` ref → silently dropped (run validate).

## Cross-links
- Route table / nested namespaces / picture upload / transport → **hoi4-build-api**.
- Field shapes + token legality → `field-reference/events.md` · `field-reference/_raw-script-fields.md` ·
  `field-reference/tokens.md`.
- Super-event field shapes (routes, the 5 text segments, upload-only picture) →
  `field-reference/super-events.md`.
- Cross-entity wiring (focus→event, event→on_actions, succession, scope-passing) → **hoi4-wiring**.
- Leader-succession characters → **hoi4-build-characters**.
- Validate on the platform (`POST export/validate` + `GET lint/tree-validation`); the in-game `error.log`
  is the final gate → **hoi4-investigate**.
