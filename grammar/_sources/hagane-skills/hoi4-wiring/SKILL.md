---
name: hoi4-wiring
description: Use when CONNECTING the platform's workbenches into live in-game behavior — a focus that fires an event, an event option that sets a flag a later focus reads, on_actions hooks (on_startup/on_monthly/…), leader succession, country renaming via cosmetic tag, scripted-snippet reuse, and the THIS/ROOT/FROM/PREV/event_target scope-passing that makes or breaks all of them. Invoke whenever a build step crosses two entities or asks "how do I make X trigger Y".
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.

# HOI4 Wiring — connect workbenches into in-game behavior

This is the **cross-cutting card** — patterns that span two entities, not one workbench's form. The
single-entity form→output maps live in **hoi4-build-focus / -events / -decisions-ideas / -characters /
-scenario / -military / -scripting / -localisation**;
the route table, auth, and payload shapes live in **hoi4-build-api**. This card carries only the canonical
cross-entity chains plus the scope discipline that makes or breaks all of them.

**Foundation (from hoi4-build-api §4):** every effect / trigger / condition field holds **raw inner HOI4
script**, and the export **wraps** it — you store `country_event = { id = ns.1 days = 3 }` in a focus's
`completion_reward`, and the export emits `completion_reward = { country_event = { … } }`. The same is true
of `available`, an option's `effects`, a decision's `complete_effect`, and so on (full field list in
`field-reference/_raw-script-fields.md`). The platform's `export/validate` checks a curated set of token
legality; **your own game's `error.log` is the final gate**. All six chains below build on that.

## 0. Before you wire — validate the token AND its scope
For every token you drop into a raw field, confirm two things:

1. **It exists and does what you think** — the reach-for-most vocabulary is in `field-reference/tokens.md`;
   for anything not listed, write it as HOI4 spells it and let the platform tell you (`POST
   /api/projects/{pid}/export/validate` + `GET /api/lint/tree-validation/{pid}`).
2. **The scope it runs in is legal for it** — the `field-reference/tokens.md` **Scopes** section maps who
   is ROOT / FROM / THIS / PREV inside each field. This catches the **#1 wiring bug**: a COUNTRY-scope
   effect run inside a STATE or iterator scope silently does nothing.

**on_action hook names (`on_startup`, `on_monthly`, `on_government_change`, …) are NOT effects or
triggers.** They are attach points on the Events workbench (the `on_action_attach` field), so they will not
appear in a token/effect list — that absence is expected, not an "invalid token" signal.

## 1. The six canonical chains (each: the token sequence + the footgun)

**CHAIN 1 — a focus completes → fires an event.** Focus `completion_reward` (raw) =
`country_event = { id = ns.N days = N }`. A bare `country_event` self-targets in the focus owner's COUNTRY
scope; wrap it in `<TAG> = { country_event = { … } }` to fire the event at a different country. **The event
and its namespace must exist first.** *Footgun:* a typo'd event id is silently dropped by the export's
cross-ref gate → the focus does nothing and no error surfaces. Run `export/validate` to catch it before the
game does.

**CHAIN 2 — a choice now branches content later (flag / variable handoff).** Producer = an event option's
`effects`: `set_country_flag = X` or `set_variable = { var = TAG_n value = N }`. Consumer = a later focus's
`available`, an event's `trigger`, or a decision's `available`: `has_country_flag = X` or
`check_variable = { var = TAG_n value = N compare = greater_than }`. *Footgun:* the flag lives on **the
country that RAN the setter** — if the option fired it inside a `FROM = { … }` or `event_target:… = { … }`
block, the reader's `has_country_flag` must run in that **same** scope. A ROOT-vs-FROM mismatch is a silent
miss. Flag / variable setters have **no auto-tooltip**, so a focus or decision whose only reward is a
variable change shows an empty effect box — fill its `effect_tooltip_locs` (the export injects a
`custom_effect_tooltip` + loc for you; see hoi4-build-api §4).

**CHAIN 3 — something fires automatically (on_startup / on_monthly / …).** Do this on the **Events
workbench**, not by hand: set the event's `on_action_attach = "on_monthly"` (or any hook) and/or
`auto_fire_on_startup = true` (+ `auto_fire_after_days`). The export builds the country's on_actions and
**auto-wraps each non-startup hook in a `tag` guard** so it fires only for the owning country instead of
worldwide — that guard is the platform's value-add here; you do not add it yourself. A self-requeuing
heartbeat re-fires itself with `country_event = { id = X days = N }` inside its own `immediate`. *Footgun:*
on_actions are inherently **global** — the reason the platform guards them for you is that an unguarded
on_action effect runs for every country in the game.

**CHAIN 4 — leader succession / allegiance flip.** Keep **one** `country_leader` character per ideology. An
event option's `effects` = `kill_country_leader = yes` + `create_country_leader = { name = … picture =
"GFX_portrait_…" ideology = <sub-ideology> traits = { … } }`. An allegiance flip with the **same** person
(no death) = `set_country_leader_ideology = <sub>` on the existing leader. *Footgun:* a second
`role_type = country_leader` character with no promoting event is a **dormant duplicate leader**, not a
successor — succession is event-driven. Full character shapes → **hoi4-build-characters** (don't duplicate
them here).

**CHAIN 5 — country rename (cosmetic tag) + dynamic modifier.** In a focus `completion_reward`, an option's
`effects`, or a decision's `complete_effect`: `set_cosmetic_tag = <COSMETIC>`; `drop_cosmetic_tag` reverts
it. *Footgun:* the cosmetic tag only swaps the **internal** tag — the visible new country name is a separate
**localisation** entry keyed by the cosmetic tag (`<COSMETIC>` and its `<COSMETIC>_DEF` adjective form).
Make sure that display-name localisation exists in **both** languages, or the country shows the raw tag.
Separately, `add_dynamic_modifier = { modifier = MOD_x days = -1 }` only **declares a slot** — the actual
modifier values must be defined first in the **Dynamic modifiers workbench** (`/dynamic-modifiers`; shape in
`field-reference/dynamic-modifiers.md`). Forget the definition and the modifier does nothing.

**CHAIN 6 — reuse + scope handoff (scripted snippets, event targets).** Define a reusable block once on the
**Scripted snippets workbench** (`/scripted-snippets`; `kind = effect|trigger`, a unique `name`, a raw
`body`), then call it from any raw field **with `= yes`**: `completion_reward = { MOD_do_x = yes }`. Pass a
target across events with `immediate = { hidden_effect = { save_event_target_as = my_target } }`, then later
`event_target:my_target = { … }`. *Footgun:* a scripted trigger/effect referenced **without** `= yes` is a
parse error; and a scripted block **inherits the caller's scope**, so a COUNTRY-scope effect called from a
STATE iterator breaks. `event_target:` **persists across events**; `PREV` / `FROM` do **not** survive a
fresh event fire. Shapes → `field-reference/scripted-snippets.md` (and `scripted-localisations.md` for
dynamic loc dispatch).

## 2. The scope-passing rule table — keep this in front of you
| Symbol | Means | Use when |
|---|---|---|
| `THIS` | the current-scope country (default, omittable) | — |
| `ROOT` | the event / focus / decision **owner** | jumping back to the source after nesting |
| `FROM` | the **caller / initiator** | the previous country in an event chain; the declaring country; in a **targeted decision**, the current target |
| `PREV` | the **previous** (enclosing) scope | inside an `any_*` / `every_*` iterator, to address the outer scope |
| `event_target:NAME` | a saved target (`save_event_target_as`) | persisting a target **across** events |

Inside an `any_country` / `every_country` / `random_country` iterator the default scope **is** the iterated
country, so `every_country = { add_stability = 10 }` is fine. The trap is **STATE iterators**
(`every_state`) — they can't run a COUNTRY effect directly; address the owner (`PREV` / `owner`).

## 3. Self-check after wiring — platform first, then your own game
1. `POST /api/projects/{pid}/export/validate` — cross-refs closed (no dropped `country_event` / focus ref),
   loc complete in both languages, assets shipped.
2. `GET /api/lint/tree-validation/{pid}` — token legality + structure. For a **submod** project with the
   base mod indexed, this lint also flags typo'd base-mod event / country_event / focus refs and unknown
   `country_tag` / `state` / `ideology` tokens as **warnings** before the game sees them. Two caveats: the
   export never drops a submod's legitimate base-mod refs, and **project-local** dangling refs are still
   silently dropped by the export cross-ref gate with no lint warning.
3. Fix everything they flag, download the ZIP, load it in **your own HOI4**, and read `logs/error.log` — the
   final gate for tokens the lint can't know about.

For each chain, confirm: the chain's tokens are present in the emitted output; a flag/var setter and its
reader are in the **same** scope; a leader succession has exactly **one** active `country_leader` per
ideology; a cosmetic rename has its display-name loc in both languages; a scripted snippet is called with
`= yes`.

## 4. Common traps (distilled)
- **Scope mismatch is the #1 wiring bug** — a flag set in `FROM = { … }` must be read with
  `FROM = { has_country_flag = X }`, not `ROOT`.
- **on_action hook names are not effect/trigger tokens** — don't try to "validate" them as tokens; they're
  the Events workbench's `on_action_attach` values.
- A typo'd `country_event` / focus ref is **silently dropped** by the export cross-ref gate — run
  `export/validate` to catch it.
- A flag- or variable-only reward has **no auto-tooltip** — fill `effect_tooltip_locs`.
- A **second same-ideology** `country_leader` is a dormant duplicate — succession must be event-driven.
- `set_cosmetic_tag` swaps the tag but **not the display name** — that needs its own cosmetic-tag loc.
- `add_dynamic_modifier` only **declares a slot** — define the modifier on the Dynamic modifiers workbench.
- A scripted snippet called **without `= yes`** is a parse error, and it **inherits the caller's scope**.
- `recruit_character` only works at **history setup** (the platform emits it there via the history-files
  workbench) — never put it in an event or on_action effect.

## Cross-links
- Route table, auth (PAT via `HOI4_PLATFORM_TOKEN`), and payload shapes → **hoi4-build-api**.
- Per-entity form→output cookbooks → **hoi4-build-focus** · **hoi4-build-events** ·
  **hoi4-build-decisions-ideas** · **hoi4-build-characters** · **hoi4-build-scenario** ·
  **hoi4-build-military** · **hoi4-build-scripting** · **hoi4-build-localisation**.
- Additive-submod build rules → **hoi4-submod**; end-to-end mod orchestration → **hoi4-mod-design**.
- Field shapes for the entities wired here → `field-reference/{events,focus,decisions,characters,dynamic-modifiers,scripted-snippets,scripted-localisations,history-files}.md`; token vocabulary + scopes → `field-reference/tokens.md`; raw-script field list → `field-reference/_raw-script-fields.md`.
