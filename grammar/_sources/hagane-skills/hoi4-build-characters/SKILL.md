---
name: hoi4-build-characters
description: Use when filling the platform's **Characters** workbench (country leaders, generals/field-marshals/admirals, political advisors, military high-command, theorists, scientists, operatives). The platform-form → HOI4-output bridge + the desired-experience cookbook + the field quirks a GET won't reveal (esp. the `traits` vs `advisor_traits` trap, dual-role merge, and event-driven succession). Invoke whenever creating/editing characters via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Character Cookbook — the Characters workbench

This is the per-entity cookbook for the **Characters** workbench: the thin bridge from the platform
form, to the HOI4 output, to the player experience. It does not re-teach HOI4 character semantics — it
carries only what a GET won't show: the form quirks, the "to get experience X fill fields Y" recipes,
the cross-entity wiring, and the validation discipline.

- **Field shapes + which HOI4 token is legal in each field** → the characters field-reference,
  `field-reference/characters.md`. (Leader/advisor traits and commander traits are *different*
  vocabularies — the field-reference lists which goes where.)
- **Transport / route table / auth (PAT-first, `Authorization: Bearer`)** → **hoi4-build-api**.
- **Cross-entity linkage (succession events, advisor gating, scope passing)** → **hoi4-wiring**.

## 1. Before you fill the form — where tokens get validated

Token legality is checked **on the platform**, not by hand:

1. `POST /api/projects/{pid}/export/validate` — cross-refs closed, loc complete in both languages.
2. `GET /api/lint/tree-validation/{pid}` — token-legality + structure.
3. Neither can know *every* engine token. After you load the exported ZIP in your own HOI4, your
   `logs/error.log` (+ `logs/game.log`) is the final gate — read it directly.

Trait vocabularies are the most common source of an invalid-token line. Check the field-reference
before inventing one — e.g. `nationalist` is **not** a vanilla trait; only compounds like
`conservative_nationalist` exist.

## 2. Platform form → HOI4 output (the mapping the GET won't explain)

`role_type` selects the PRIMARY block; `has_advisor_role=True` adds an advisor block on top of it.

| Platform `role_type` | HOI4 block emitted | skill fields used | traits read from |
|---|---|---|---|
| `country_leader` | `country_leader = { ideology=… traits=… }` | — (needs `ideology`) | `traits` |
| `general` | `corps_commander = {…}` | skill/attack/defense/planning/logistics | `traits` |
| `field_marshal` | `field_marshal = {…}` | same | `traits` |
| `admiral` | `navy_leader = {…}` | skill/attack/defense/maneuvering/coordination | `traits` |
| `advisor` | `advisor = { slot=… traits=… }` | advisor_slot/advisor_cost/advisor_modifier | **`traits`** (NOT `advisor_traits`!) |
| `scientist` / `operative` | `scientist`/`operative` block | scientist_data / operative_* | `traits` |

- **🔴🔴 The single biggest trap: a PURE advisor's trait is read from `traits`, NOT `advisor_traits`.**
  The platform will fall back to `advisor_traits` when `traits` is empty, but `traits` **wins** when
  both are filled — so **always put the advisor's trait in `traits`** for round-trip symmetry with
  import. (Optionally also set `advisor_modifier` as raw script, e.g. `political_power_factor = 0.1`,
  for an explicit extra effect on top of the trait.)
- **`country_leader` emits ONLY when `role_type=="country_leader"` AND `ideology` is set.** A general
  carrying a leftover `ideology` will not wrongly emit a leader block (it's guarded), but DO clear
  `ideology` when you demote a leader → advisor, so a stale leader-only trait doesn't ride along in
  `traits`.
- **Portrait:** `large_portrait` drives the `portraits` block, and the export re-files the image under
  the char's real `country_tag` automatically. Upload the image with
  `POST /api/projects/{pid}/characters/{id}/upload-portrait`; leave it empty for a minor/institutional
  officer to get the vanilla generic portrait. **`POST /characters` requires a top-level `name` field**
  (422 without it — `name_en`/`name_zh` don't substitute). The platform auto-emits `recruit_character`
  for every char you create; you don't wire that yourself.

## 3. Want experience X → fill fields Y (cookbook)

- **Political advisor that boosts the economy / PP** → `role_type=advisor`,
  `advisor_slot=political_advisor`, **`traits=["silent_workhorse"]`** (PP) / `captain_of_industry`
  (civ build) / `war_industrialist` (mil build) / `smooth_talking_charmer` (relations).
- **Army/navy/air high-command bonus** → `role_type=advisor`,
  `advisor_slot=army_chief`/`navy_chief`/`air_chief`, `traits=["army_chief_offensive_2"]` /
  `navy_chief_decisive_battle_2` / `air_chief_ground_support_2`. (Air force is commanded via
  `air_chief`, NOT a field commander — there is no "air general" role.)
- **A person who is BOTH a recruitable general AND a high-command advisor** → **ONE character**:
  `role_type=general` + skills + `traits=[<commander trait>]` + `has_advisor_role=True` +
  `advisor_slot=army_chief`. **Do NOT create two same-named characters** (one general, one advisor) —
  that makes the same person appear twice in-game.
- **Leader succession (a successor takes over on an event)** → keep **ONE** `country_leader` char; the
  event effect does `kill_country_leader = yes` + `create_country_leader = { name=… ideology=… }`. **Do
  NOT pre-create a 2nd `country_leader` "for succession"** — with no event to promote it, it's just a
  dormant duplicate leader of the same ideology. (Ideology-switch endings use
  `set_country_leader_ideology` on the *existing* leader — no extra char needed.)
- **Placeholder art vs a real face** → a named historical figure → upload a portrait image via the
  `upload-portrait` endpoint above; a minor/institutional officer → leave the portrait empty for the
  vanilla generic.

## 4. Wiring out (→ hoi4-wiring)

- The `country_leader` you create is the **active** leader at start; alternative leaders are promoted
  by events (`create_country_leader` / `promote_character` / `set_country_leader_ideology` placed in an
  event or focus effect field).
- **One active `country_leader` per ideology.** A 2nd same-ideology `country_leader` char is a dormant
  duplicate, not a successor — succession is event-driven (see §3).
- **Referencing a base-mod / vanilla character that isn't a project entity (e.g.
  `promote_character = <vanilla_id>`) is DROPPED by the export's cross-ref gate** — the gate only keeps
  references to entities that exist in *your* project. For a vanilla-portrait successor, use
  `create_country_leader = { name="…" picture="GFX_Portrait_…" ideology=… }` inline in the event/focus
  effect — it references no project char, so nothing is gated, and it emits the vanilla portrait
  directly. (Conversely, setting a project char's `large_portrait` to a `GFX_` sprite *token* isn't
  emitted — the portrait pipeline expects an uploaded image, not a raw sprite reference — which is the
  other reason to use the inline `create_country_leader` form for a vanilla-art leader.)
- **`advisor_available` / `advisor_visible` hold raw triggers** (e.g. `has_completed_focus = X`) —
  this is how a focus/event "unlocks" an advisor.
- **When your leader competes with a same-ideology base-mod leader**, HOI4 auto-picks by ideology at
  start and will often pick the base-mod one. To force *your* latent leader active at 1936, put
  `promote_character = <your_char_id>` in the **bookmark effect block** (it runs after history, before
  country-selection — see hoi4-build-api's bookmarks route), NOT by adding a second duplicate leader.

## 5. Self-check after building (entity-level)

GET your created characters back and assert:

- `role_type` / `advisor_slot` persisted;
- **every advisor has a non-empty `traits` (or an `advisor_modifier`)** — otherwise it has no effect;
- no two characters share a display name in the same country (unless it's an intentional
  one-char-two-roles merge).

Then run `export/validate` + the tree-validation lint, and treat the author's in-game `error.log` as
the final gate.

## 6. Common traps (distilled)

- **Pure advisor with only `advisor_traits` filled** → put the trait in `traits` instead (`traits`
  wins; `advisor_traits` is only a fallback).
- **`nationalist` / other non-existent trait** → invalid-trait line in `error.log`; check the vocabulary
  in `field-reference/characters.md`.
- **Two same-named chars for one dual-role person** → the same person appears twice in-game; merge into
  one char with `has_advisor_role=True`.
- **2nd same-ideology `country_leader` with no promoting event** → dormant duplicate; use event-driven
  succession.
- **Missing top-level `name`** → 422.
- **Institutional / collective names as advisors** read oddly as commander candidates — prefer real
  people.
