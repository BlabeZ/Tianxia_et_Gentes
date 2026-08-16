---
name: hoi4-submod
description: Use when building or extending a dependency-style submod on the platform (a project that declares dependencies on a base mod like TNO/KR/TFR and references its characters, tech, art, and ideologies). Covers the additive-on-canon architecture, the base-mod reference-index workflow, the base-mod-idiom toolkit (leader switch / rename / death) done via API, asset handling, and the hard append-only boundary. Invoke when the task is "make / add content to a submod of <base mod>".
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.

# HOI4 Submod — build a dependency-style submod the right way

A submod declares a `dependency` on a base mod (TNO / KR / TFR / …) and references its characters,
focuses, ideologies, and art. The platform builds these **additively**: everything you create is
appended on top of the base mod's content and rides its canon. The one rule that prevents most of the
pain:

> **ADD content and ride the base mod's canon — never try to suppress base-mod behavior. The platform
> is append-only; it structurally cannot cancel or disable what the base mod already ships.**

## When to use
- Building or extending a project that declares `dependencies` on a base mod and references its tokens.
- Any "make Germany do X / add a focus tree / add the Speer→Brandt arc" on a base-mod-dependent project.
- Scoping a submod feature — settle the architecture (it is always additive) before you build.

For the route table, payload shapes, transport, and export idioms → **hoi4-build-api**. For end-to-end
orchestration of a whole mod → **hoi4-mod-design**. This skill covers what is *submod-specific*.

## 1. Architecture is additive-on-canon — there is no other mode
- ✅ **Additive** = sit your content on top of / after the base mod's existing state and story beats.
  Hook onto the flags, events, and on_actions the base mod *emits*, and add your own reactions.
- ❌ **Suppress / override** = trying to disable, cancel, or replace a base-mod event, on_action, or
  start-state. The platform cannot emit this — it only appends. HOI4 itself has no `disable_event`,
  on_actions are append-only, and already-scheduled events cannot be cancelled.

So **design additively from the start.** If a beat seems to need suppression, redesign it as a reaction:
trigger-denial via an `on_startup` flag works when the target event has a checkable `trigger { }` you can
gate against, but it does nothing to an unconditional, trigger-less scheduled event. Build *around* the
base mod's canon, not against it.

## 2. Project setup + ingest the base-mod reference index
1. **New EMPTY project** — do not import the whole base mod. Reference its tokens directly; they load at
   runtime. Do not copy its art (see §6).
2. **Declare the exact `dependencies`** name the base mod ships under, and align the project's
   `supported_version` to the base mod's game version. A version mismatch is a common CTD.
3. **Ingest the base-mod reference index once.** `POST /api/projects/{pid}/import/basemod-index` parses
   the base mod into an index and discards the content — it is **index-only** and never imports the base
   mod's entities into your project. The index is shared per-dependency, so a second submod of the same
   base mod reuses it.

After ingest, the platform *knows* the base mod, and two things turn on:
- **Reference pickers autocomplete real base-mod entities** — character / focus / decision / idea /
  `country_tag` / ideology / state — via `GET /api/projects/{pid}/import/basemod-index/refs` and
  `.../basemod-index/ideology-registry`.
- **Base-mod-aware lint** catches an undefined base-mod TAG / state / ideology / focus / decision typo at
  build time, instead of the export silently dropping the dangling ref. Un-indexed submods fall back to
  trust-all (no false flags), so indexing is strictly an upgrade.

Use the index instead of guessing base-mod token names — it is the authoritative source for how the base
mod actually spells its entities.

## 3. Build via the authenticated API
Drive the workbenches through the API — routes, payload field shapes, and export-emission idioms are all
in **hoi4-build-api**. Auth is **PAT-first**: base URL from `HOI4_PLATFORM_URL`, and
`Authorization: Bearer <token>` from `HOI4_PLATFORM_TOKEN` on every call. No password ever touches a
script.

## 4. Base-mod-idiom toolkit — match how the base mod does it, via API
Character and regime operations have exact effect tokens; the wrong one is rejected at load. The
base-mod index's `ideology-registry` and `refs` tell you the real tokens to plug in.

- **Leader switch = `promote_character = { ideology = <subtype> }`** on the character scope, to *activate*
  a character's pre-existing latent `country_leader` role. **Never `add_country_leader_role`** on a
  character who already has one — HOI4 rejects it ("already has a country leader role") and the promote
  fails.
- **Rename = `set_character_name = <char_token>`** (plus `set_portraits` if the portrait changes).
- **Death / succession = `kill_country_leader = yes`.** Succession is event-driven — one active
  `country_leader` per ideology, so a second same-ideology leader is a dormant duplicate, not a
  successor; hand off with `kill_country_leader` + `create_country_leader` in an event (see
  hoi4-build-characters).
- **Group vs subtype:** `set_politics = { ruling_party = <GROUP> }` takes the ideology **GROUP**;
  `ideology = …` and `promote_character = { ideology = … }` take the **SUBTYPE**. Base mods often redefine
  the ideology space — TNO, for instance, has no vanilla `democratic` / `communism` / `neutrality`
  groups — so read the index's `ideology-registry` before choosing, rather than assuming vanilla names.
- **Swap a base nation's focus tree** by emitting `load_focus_tree = <your_tree>` at the right time (via a
  focus reward or an `on_startup` event effect). An explicit `load_focus_tree` wins over tree scoring, so
  it cleanly hands the nation your tree without touching the base mod's.

These effect strings go into the platform's raw-script effect fields, which the export wraps for you (see
hoi4-build-api §4 and `field-reference/_raw-script-fields.md`).

## 5. States / territory — never write a state file from memory
Map changes (ownership, cores, buildings, renames) have a first-class platform route. Use it — do not
reconstruct vanilla state files by hand.

**Preferred — platform route (MCP or REST, same data):**
1. `seed_states_from_vanilla(state_ids=[...])` — copies the real vanilla state definitions (provinces,
   manpower, buildings, exact source filename) into your project from the platform's
   current-game-version snapshot. A fresh project has 0 states; seeding is how states enter it.
2. `get_states(name_query="Borneo")` — find states by real geographic name. Rows carry
   `display_name_en` / `display_name_zh`; `name_query` matches the en/zh name, the raw `STATE_<id>` loc
   key, or an exact state id.
3. `edit_state(state_id=…, owner=…, add_core_of=[…], buildings=…, display_name_en=…, display_name_zh=…)`
   — change what you need. `display_name_*` renames the state as a pure **localisation override**; the
   state file's `name = "STATE_<id>"` loc key never changes.
4. Export — the platform emits your edited state under the **vanilla original filename** (so it
   filename-shadows vanilla's file and exactly one definition wins) and ships the rename as a
   `STATE_<id>: "New Name"` loc override. ⚠️ Never hand-write the `:0`-versioned form
   (`STATE_<id>:0 "…"`) — tested in-game it triggers a loc-key collision that vanilla wins, so the
   rename silently does nothing.

The data comes from the platform's snapshot of the current game version, so this route is immune to
version drift by construction.

**Fallback — local game files:** only when a real HOI4 install exists on THIS machine. Copy the vanilla
state file byte-for-byte **including its exact, irregular original filename** (`333-British Borneo.txt`
vs `1023 - Brunei.txt` — record verbatim, never synthesize), edit only `owner` / cores, and KEEP the
`provinces = { … }` block untouched.

**Iron rules — each one is a real conflict/CTD class:**
1. ⚠️ **Never write a `provinces = { … }` block from memory.** Province lists must come from the seed
   tool or a real game file on disk. LLM recall of state compositions is stale by construction; a
   memory-written state double-defines provinces against the current map → province tug-of-war,
   ownerless provinces, likely CTD.
2. ⚠️ **Renaming a state = `display_name_*` / loc override only.** Never change the
   `name = "STATE_<id>"` loc key inside the state definition.
3. ⚠️ **Before `create_country`, check the tag isn't already a vanilla country.** The vanilla roster
   grows with patches (BRN = Brunei ships in vanilla since 1.18) — re-creating an existing tag →
   `Duplicate Country Tag`.
4. ⚠️ **State layouts drift across game versions** (333 British Borneo → split into three states in
   1.16 → Southeast Asia redrawn again in 1.19). Whatever your training memory holds, the platform's
   data is ground truth — read before writing.

🚩 **A fresh custom tag owns nothing in vanilla → it is "dead" at start** (not listed in the bookmark,
`on_startup` never fires) until some state owns to it. Fix via the same route:
`seed_states_from_vanilla` the target states, then `edit_state(owner=<TAG>)`.

Field shapes and the full workflow → `field-reference/states.md`.

## 6. Assets via upload, never base-sprite refs
Ship your own icon/portrait/picture bytes through the upload endpoints — referencing a base-mod sprite
name gets dropped at export and the slot shows a "?" placeholder.
- Spirit / idea icon: `POST /ideas/{id}/upload-picture` (multipart; a tall ~65:67 image with alpha reads
  correctly in the spirit slot).
- Event picture: `POST /events/{id}/upload-picture`. Character portrait:
  `POST /characters/{id}/upload-portrait`. Focus node icon: `POST .../nodes/{id}/upload-icon`.

## 7. Super-event scheduling — a quirk a GET won't reveal
`auto_fire_on_startup` is the **enable-the-scheduler switch, not "fire on day 1."** A delayed super-event
= `auto_fire_on_startup = true` **plus** `auto_fire_after_days = N`. Setting `auto_fire_on_startup = false`
to *get* a delay instead makes the whole super-event silently vanish from the export (a dormant-drop, no
warning).

## 8. Verify on the platform, then in your own game
1. `POST /api/projects/{pid}/export/validate` — cross-refs closed, loc complete in both languages, assets
   shipped.
2. `GET /api/lint/tree-validation/{pid}` — token-legality + structure.
3. Fix everything they flag, then download the ZIP, load it in your own HOI4, and read `logs/error.log` —
   the final gate for tokens the lint cannot know about. Grep it for **your** tokens (tag, focus/event
   ids, ideology, state ids); base-mod animation/entity noise is not yours. `logs/text.log` surfaces loc
   collisions.

**Verifying a long-delayed outcome** (a super-event scheduled hundreds of days out)? Don't make the
tester fast-forward years. In a test build, temporarily retime the trigger (e.g. drop
`auto_fire_after_days` to ~7) so the whole chain plays out in minutes, verify it, then restore the real
value before shipping.

## Gotchas / anti-patterns
- 🚩 **Trying to suppress a base-mod event / on_action.** There is no `disable_event`; on_actions and
  scheduled events are append-only. Redesign additively (§1).
- 🚩 **`add_country_leader_role` on a character who already has that role** → rejected, promote fails. Use
  `promote_character` on the existing role instead.
- 🚩 **`set_politics { ruling_party = <subtype> }`** → takes the GROUP, not the subtype. Subtype goes on
  `ideology =` / `promote_character { ideology = }`.
- 🚩 **Referencing a base-mod sprite for your own icon/portrait** → dropped at export, shows "?". Upload
  your own bytes (§6).
- 🚩 **`auto_fire_on_startup = false` for a delayed super-event** → the whole super-event is silently
  dropped. Use `true` + `auto_fire_after_days` (§7).
- 🚩 **Adding a national spirit / idea that you only want to attach later.** Set the idea's
  `auto_attach_on_start = false` (per-idea toggle, default `true`) so it does not appear on the country at
  game start; attach it on schedule via a focus/event `add_ideas` instead.
- 🚩 **Relying on a base-mod hook that the base mod disabled.** Some base mods comment out hooks like
  `on_ruling_party_change`, so they never fire. Confirm your intended hook actually fires before building
  on it — prefer your own `on_monthly_<TAG>` / `on_weekly_<TAG>` reactions (append-only, yours to own).
  See hoi4-wiring for scope-passing and on_actions.
- 🚩 **Trusting "export succeeded."** Run validate + lint (§8) and read your own game's `error.log`; a
  typo'd cross-ref is dropped silently and only shows up in-game.
- 🚩 **Hand-writing a vanilla state file from memory** → stale province list → double-defined provinces →
  tug-of-war / CTD. Seed from the platform instead (§5).
- 🚩 **`create_country` with a tag vanilla already ships** (e.g. BRN since 1.18) → `Duplicate Country
  Tag`. Check the vanilla roster / base-mod index first (§5 iron rule 3).

## Cross-links
- Routes, payload shapes, transport, export idioms → **hoi4-build-api**.
- End-to-end mod orchestration → **hoi4-mod-design**.
- Per-entity cookbooks → **hoi4-build-characters** · **hoi4-build-focus** · **hoi4-build-events** ·
  **hoi4-build-decisions-ideas** · **hoi4-build-scenario** · **hoi4-build-military** ·
  **hoi4-build-scripting** · **hoi4-build-localisation** · cross-entity wiring → **hoi4-wiring**.
- Field meanings + platform quirks per workbench → `field-reference/<workbench>.md`.

→ Pick additive-on-canon, ingest the base-mod index, match the base mod's own idioms via API, upload your
own assets, validate on the platform, then test it in your own HOI4 (read `logs/error.log`).
