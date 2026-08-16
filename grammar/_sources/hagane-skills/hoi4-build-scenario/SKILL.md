---
name: hoi4-build-scenario
description: Use when filling the HOI4 mod platform's **Scenario & Start State** workbenches — creating countries (custom TAGs, flags, per-ideology names), bookmarks (the scenario/country-select screen, playable-nation list, start date, the startup `effect` block), history files (a country's day-0 start state — ruling party, popularities, starting ideas/techs, capital, diplomacy), states (territory: owner/cores/manpower/buildings/VPs — EDIT-only, seed from vanilla first), and the project-level ideology registry (custom sub-ideologies). The platform-form → in-game bridge + the cookbook + the quirks a GET won't reveal (esp. sentinel values in history files, the states seed-before-edit rule, TAG collision/length traps, and regime-flip-at-startup via the bookmark effect). Invoke whenever creating/editing countries, bookmarks, history files, or states via the API.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Scenario & Start State

> **A "build card" = the thin bridge between the platform form, the HOI4 output, and the player
> experience.** It does NOT re-teach the full field tables — `field-reference/countries.md`,
> `field-reference/bookmarks.md`, `field-reference/history-files.md`, `field-reference/states.md`, and
> `field-reference/ideologies.md` already map every field to its HOI4 token. This card carries only the
> per-workbench emission map, the cookbook (headline: the full "playable custom country" chain), the
> wiring, and the validation discipline.
>
> Route table / transport / flag & picture uploads → **hoi4-build-api**. Cross-entity wiring (cosmetic
> tags, startup on_actions, flag/variable plumbing) → **hoi4-wiring**. Leaders and advisors →
> **hoi4-build-characters**. Division templates + deployments (the OOB the history file points at) →
> **hoi4-build-military**.

## 0. Before you fill the form — two validation sources
1. **Read the field-reference file for the workbench you're touching** (`countries.md` / `bookmarks.md` /
   `history-files.md` / `states.md` / `ideologies.md`) for field shapes, sentinels, and quirks.
2. **These workbenches are almost entirely structured** — very little raw script. The exceptions: the
   bookmark `effect` block, the history file's generic `raw_script` escape-hatch, and states'
   `impassable_ignored_links` raw inner list. Validate any token you put there against
   `field-reference/tokens.md`, then run the platform gates
   (`POST /api/projects/{pid}/export/validate` + `GET /api/lint/tree-validation/{pid}`); the in-game
   `logs/error.log` is the final gate. Remember: the bookmark `effect` and history script run in
   COUNTRY scope (per-TAG blocks); state history runs in STATE scope.

## 1. Platform form → HOI4 output (the mapping the GET won't explain)

### Countries (`/countries`) — the scope anchor; create these FIRST
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `tag` | the country TAG — `common/country_tags` entry + `common/countries/` definition + everything downstream scopes to it | 🔴 The platform form accepts 2–5 chars, but **the engine requires exactly 3** — a 2-letter TAG passes the form and **silently breaks in-game**. Use 3 letters/digits, starting with a letter. **Reusing a vanilla TAG is deliberate "replace that vanilla country"** (allowed, soft warning); an *accidental* collision means `owner = <TAG>` binds to the existing vanilla nation — confirm the tag is free before POSTing. |
| `name` (+ `name_en`/`name_zh`) | country display-name loc in both languages | Fill both languages (symmetric loc discipline, same as every workbench). |
| `color` / `color_ui` | `color = { r g b }` (+ optional `color_ui`) | `color_ui = []` **clears** an override (falls back to `color`) — it's not a no-op. |
| `ideology` | the country's default ruling ideology | 🔴 This is the **GROUP** (`neutrality`/`democratic`/`communism`/`fascism`), never a sub-ideology. The sub-ideology is picked by the leader character / history file. |
| `name_neutrality` / `name_democratic` / `name_communism` / `name_fascism` (+ `*_zh`) | per-ideology country-name loc overrides | The name the country shows under each government — the cheap way to get "Empire under fascism, Republic under democracy". |
| `flag_image_path` / `POST /countries/{id}/upload-flag` | `gfx/flags/<TAG>.tga` | No flag → the in-game placeholder. Upload resizes to the engine's 82×52. |

### Bookmarks (`/bookmarks`) — the scenario-select screen
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `bookmark_id` + `date` | `bookmarks = { bookmark = { name=… date=… } }` | Date default `1936.1.1.12`. The id is a script token — keep it mod-prefixed. |
| `name_en/zh` / `desc_*` | bookmark title/subtitle loc | Both languages. |
| `picture` | backdrop sprite (default `GFX_select_date_1936`) | Or upload via the bookmark's `upload-picture`. |
| `default_country` / `default_flag` | pre-selected nation / default bookmark marker | `default_country` auto-shows on the screen — but ALSO list it in `selectable_countries` if it needs its own blurb/labels. |
| `selectable_countries` (`list[dict]`: `{tag, history_en, history_zh, minor, label:[...]}`) | the playable-nation rows + hover blurbs | Featured (big-portrait) nations **omit** `minor`; small-flag rows set `minor: true`. 🔴 There is NO `major` key — writing one errors in-game. `label` = focus-icon slots on the card — the panel has limited slots, don't overfill. |
| `effect` (RAW) | `effect = { … }` inside the bookmark | 🔑 **Runs AFTER all history files, BEFORE country selection** — the one place to fix up the select screen itself. See the regime-flip recipe (§2). |
| `filters` | `filters = { … }` (1.19 tokens: `new_content` / `continent`) | Structured, emitted as-is. |

### History files (`/history-files`) — one per country, day-0 start state
| Platform field | HOI4 output | Quirk |
|---|---|---|
| `country_tag` | targets `history/countries/<TAG> - *.txt` | 🔴 **One per country** — a duplicate `country_tag` is a 409. PUT the existing one instead. |
| `capital` | `capital = <state_id>` | A **state id**, not a province. 🔴 `0` = sentinel "don't emit". The country must OWN that state (see §2) or the game logs `capital … they don't own it`. |
| `set_politics_ruling_party` + election fields | `set_politics = { ruling_party=… elections_allowed=… … }` | Ruling party = ideology **group**. Pair with popularities. |
| `set_popularities_*` (democratic/communism/fascism/neutrality) | `set_popularities = { … }` | Should sum to 100. |
| `set_stability` / `set_war_support` | `set_stability = N` / `set_war_support = N` | 🔴 `-1.0` = sentinel "don't emit", not a real value. |
| `add_ideas_extra` / `remove_ideas` | `add_ideas = { … }` / `remove_ideas = { … }` | Starting national spirits, economy/conscription laws → ids from your Ideas workbench or vanilla. |
| `complete_national_focus_ids` / `set_technology_ids` / `set_research_slots` | pre-completed focuses / `set_technology = { … }` / `set_research_slots = N` | Ids must exist (your tree/techs or vanilla). |
| `set_cosmetic_tag` | `set_cosmetic_tag = <TAG>` | Day-0 rename/reskin — the cosmetic-tag chain lives in **hoi4-wiring**. |
| `set_oob` / `set_air_oob` / `set_naval_oob` | `oob = "…"` etc. | File-stem pointers into the OOB generated from division deployments → **hoi4-build-military**. |
| `set_autonomy` / `diplomatic_relation` (`list[dict]`) | structured subject/diplomacy blocks | Puppet chains, non-aggression, relation boosts at start. |
| `startup_flags` | `set_country_flag = …` lines | Day-0 flags your events/decisions read later → **hoi4-wiring**. |
| `raw_script` (escape-hatch) | appended verbatim to the history file | Prefer the structured fields; validate any token you put here (§0). |

### States (`/states`) — territory · 🔴 EDIT-only
| Platform field | HOI4 output | Quirk |
|---|---|---|
| *(creation)* | — | 🔴 **You cannot create a state.** A fresh project has no states: first `POST /states/seed-from-vanilla` (`{state_ids:[...]}` or `{all:true}`) — it copies the real vanilla definitions (provinces, buildings, exact vanilla filename) — then PUT your changes. Imported-mod projects already have theirs. |
| `owner` / `controller` | `owner = TAG` / controller block | `controller` nullable = no distinct occupier. |
| `add_core_of` / `add_claim_by` / `remove_core_of` (`list[TAG]`) | `add_core_of = TAG` … | Core = the population fights for you; no core = resistance + tiny manpower. |
| `manpower` / `resources` / `state_category` | direct | `state_category` is free text, not an enum. |
| `buildings` / `province_buildings` / `victory_points` / `set_province_controller` | state-history blocks | Structured dicts/lists — shapes in `field-reference/states.md`. |
| `impassable` / `impassable_ignored_links` | `impassable = yes` + raw inner list wrapped | — |
| `display_name_locs` `{"en","zh"}` | a `STATE_<id>` **loc override** (never touches the state file's `name` key) | 🔴 Replace-whole-dict on PUT. The export emits the bare `STATE_<id>: "…"` line for you — no version suffix (a `:0` suffix makes vanilla win and the rename silently fails). |
| *(export)* | each edited state ships under its **vanilla original filename** | Same-name shadowing = exactly one definition wins. Handled for you — but it's why you must never hand-write a `provinces = { … }` block from memory (version-stale province lists → double-defined provinces → tug-of-war / CTD). |

### Ideology registry — on the PROJECT, not a route
`GET /api/projects/{pid}` → `ideology_registry`; update via `PUT /api/projects/{pid}` with
`{"ideology_registry": {"sub_ideologies": [{id, group, name:{en,zh}, desc:{en,zh}}]}}`. Custom content =
**sub-ideologies inside the vanilla 4 groups**, add-only on top of the vanilla vocabulary; every
sub-ideology dropdown (characters, countries) reads from it. On export (standalone project) the platform
emits the complete ideologies file + the `replace_path` + the loc for you — **never hand-write a raw
fragment that re-opens a vanilla group** (engine: `Duplicate database id` → whole block discarded →
leaderless country). Full mechanics + the failure cascade → `field-reference/ideologies.md`.

## 2. Want experience X → fill fields Y (cookbook)

- **🔑 HEADLINE: a playable custom country (the full chain)** — four steps, in order; skipping one gives
  a country that exists but can't be played sanely:
  1. **Country**: POST `/countries` `{tag:"XYZ" (3 chars, vanilla-free), name_en/zh, color, ideology:<group>}`;
     upload a flag.
  2. **Territory**: seed the states it starts with (`POST /states/seed-from-vanilla`), then PUT each:
     `{owner:"XYZ", add_core_of:["XYZ"]}` — owned AND cored, including the capital state.
  3. **History file**: POST `/history-files` `{country_tag:"XYZ", capital:<owned state id>,
     set_politics_ruling_party:<group>, set_popularities_*:(sum 100), set_research_slots:3,
     add_ideas_extra:[...], set_technology_ids:[...]}`.
  4. **Faces & fists**: a `country_leader` character for the ruling group (→ **hoi4-build-characters**)
     and, optionally, division templates + deployments wired to `set_oob` (→ **hoi4-build-military**).
  Optionally step 5: list it in a bookmark (below) so players can find it.
- **A scenario-select entry (bookmark) featuring your nations** → POST `/bookmarks`
  `{bookmark_id:"mymod_1936", date:"1936.1.1.12", name_en/zh, desc_en/zh, default_country:"XYZ",
  selectable_countries:[{tag:"XYZ", history_en/zh:"<hover blurb>", label:[...]}, {tag:"GER", minor:true, …}]}`.
  Featured nations omit `minor`; everyone else gets `minor:true`.
- **Flip a regime at startup (and have the select screen agree)** → the bookmark `effect` block runs
  after history, before country selection — so a history-file politics setup alone can leave the select
  screen showing the OLD leader. Put the fix-up in `effect`:
  `XYZ = { set_politics = { ruling_party = communism elections_allowed = no } promote_character = <char_id> }`.
  Per-TAG blocks, one per country you're flipping. (Character ids → **hoi4-build-characters**.)
- **Transfer land between existing countries** → seed the states involved, PUT
  `{owner:"NEW"}` (+ `add_core_of:["NEW"]` if it should be core land, `add_claim_by:["OLD"]` if the
  loser should want it back). Never touch provinces.
- **Rename a state** → PUT `display_name_locs: {"en":"…","zh":"…"}` (whole dict). Nothing else — the
  export handles the loc-override plumbing.
- **A custom sub-ideology (e.g. a flavored monarchism)** → PUT the project's
  `ideology_registry.sub_ideologies` entry, then use its id on your leader character and reference the
  **group** in country `ideology` / history `set_politics_ruling_party`. The subtype's name shows on
  the leader's ideology-icon hover; the politics-screen "Ideology" line stays the group name.
- **A starting puppet / faction web** → history file `set_autonomy` (subject setup) +
  `diplomatic_relation` list entries on the overlord/neighbors.
- **Day-0 story hooks** → `startup_flags` on the history file set the flags; your events/decisions read
  them (`has_country_flag`) → **hoi4-wiring**. For "an event fires at game start", prefer the event's
  own `auto_fire_on_startup` (→ **hoi4-build-events**) over history script.

## 3. Wiring out (→ hoi4-wiring)
- The country TAG is the universal scope anchor: focus trees bind via their `country` field, events fire
  at it, decisions target it. Create the country FIRST; everything else references the tag.
- History `set_cosmetic_tag` / mid-game `set_cosmetic_tag` in effects = the rename/reskin chain (full
  recipe in **hoi4-wiring**).
- History `startup_flags` → read later by focus/decision/event `available`/`trigger`.
- Bookmark `effect` is the same effect language as everywhere else — anything legal in COUNTRY scope
  works, but keep it to select-screen fix-ups (politics, `promote_character`); gameplay content belongs
  in focuses/events.
- `set_oob` names must match the deployment set built in **hoi4-build-military** — a pointer to a
  nonexistent OOB stem is silent in export, loud in-game.
- **Submod projects**: base-mod tags, states, and ideology space are inherited — reference the base
  mod's ids directly, and remember the additive boundary (append, don't suppress) → **hoi4-submod**.

## 4. Self-check after building (entity-level)
GET everything back and assert: the TAG is 3 chars and either vanilla-free or a deliberate replacement;
every state the history file's `capital` and your recipe rely on is seeded, owned, and cored; popularity
fields sum to 100; no sentinel left where you meant a real value (`capital=0`, stability/war-support
`-1.0` mean "don't emit"); exactly one history file per tag; every bookmark `selectable_countries` tag
exists; both loc languages filled everywhere. Then run `POST /api/projects/{pid}/export/validate` +
`GET /api/lint/tree-validation/{pid}` — cross-refs closed, loc symmetric — before the in-game pass
(`logs/error.log` is the final gate).

## 5. Common traps (distilled)
- 🔴 **2-letter TAG**: the form accepts it, the engine doesn't — silently broken in-game. Exactly 3.
- 🔴 **Accidental vanilla-TAG collision**: your content binds to the existing vanilla country. Deliberate
  reuse = the "replace vanilla" pattern; accidental = check first (pinyin 3-letter tags collide a lot).
- 🔴 **States are EDIT-only**: no seed → no states → PUTs have nothing to hit. Seed from vanilla first;
  never hand-write `provinces = { … }` from memory (version-stale → double-defined provinces → CTD).
- 🔴 **Capital not owned/cored** → in-game `capital … they don't own it`. Own + core the capital state.
- 🔴 **Sentinels**: history `capital=0`, `set_stability=-1.0`, `set_war_support=-1.0` = "don't emit".
- 🔴 **Second history file for the same tag** → 409. PUT the existing one.
- 🔴 **Regime flipped in history but select screen shows the old leader** → the fix lives in the
  bookmark `effect` (runs after history, before selection), not in more history script.
- 🔴 **Raw ideology fragment re-opening a vanilla group** → `Duplicate database id`, whole block
  discarded, leaderless country. Use the project `ideology_registry`.
- Bookmark `selectable_countries`: no `major` key exists (featured = omit `minor`); `label` slots are
  limited; state renames take **no `:0` suffix** (the platform emits it correctly — don't fight it via
  raw loc).
- `ideology` on the country / `set_politics_ruling_party` = the GROUP; sub-ideologies live on the
  leader character + the project registry.

## Cross-links
- Route table / transport / uploads (flag, bookmark picture) → **hoi4-build-api**.
- Field shapes → `field-reference/countries.md` · `bookmarks.md` · `history-files.md` · `states.md` ·
  `ideologies.md` · token legality → `field-reference/tokens.md`.
- Cosmetic tags, startup hooks, flag/variable plumbing → **hoi4-wiring**.
- Leaders / advisors for the new country → **hoi4-build-characters**.
- Division templates, deployments, and the OOB the history file points at → **hoi4-build-military**.
- Additive rules + base-mod inheritance for submods → **hoi4-submod**.
- Validate on the platform (`POST export/validate` + `GET lint/tree-validation`); the in-game
  `error.log` is the final gate → **hoi4-investigate**.
