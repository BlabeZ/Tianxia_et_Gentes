---
name: hoi4-build-api
description: Use when about to DRIVE the HOI4 mod platform's workbenches via authenticated API to build mod content (create/update focus nodes, events, characters, ideas, decisions, countries, then export) — the route table + payload shapes + export-emission idioms, so you build correctly through the platform instead of guessing. Invoke whenever hoi4-submod or hoi4-mod-design reaches the "build via API" step, or you need the route/field shape for a workbench entity.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.

# HOI4 Build API — drive the platform's workbenches

The build skills (`hoi4-submod`, `hoi4-mod-design`) say "build via authenticated API". This is the
**reference card** for that API surface. Everything you build here renders live in the platform's web
editor and exports as a clean, load-order-correct mod ZIP — that's the whole point of building on the
platform instead of hand-writing files.

## 1. The protocol that never rots: GET to learn the shape, then POST it back
The API is RESTful + uniform per workbench:
- `GET /api/projects/{pid}/<resource>` → list ; `GET .../<resource>/{id}` → one (the **exact field shape**)
- `POST /api/projects/{pid}/<resource>` → create. **Body = the same fields you see in GET, minus the server-assigned `id`.** Defaults fill anything you omit.
- `PUT /api/projects/{pid}/<resource>/{id}` → **partial** update (send ONLY the changed field).
- `DELETE .../<resource>/{id}`.

So to build any entity you're unsure about: **GET an existing one (or the list), copy its field shape,
POST the same shape.** This reads the live schema, so it survives platform updates. The rest of this card
is the fast-path (route table) + the idioms a GET does NOT reveal.

**What each field MEANS + which HOI4 token is legal in it** → read `field-reference/<workbench>.md`
(bundled). A GET shows the platform's field *shape*; the field-reference maps HOI4's tokens onto those
fields and flags the platform quirks behind them. **Per-entity cookbooks** (the platform-form → in-game
→ player-experience bridge): **hoi4-build-focus** · **hoi4-build-events** (incl. super-events) ·
**hoi4-build-decisions-ideas** · **hoi4-build-characters** · **hoi4-build-scenario** (countries,
bookmarks, history files, states) · **hoi4-build-military** (tech, equipment, divisions, OOB, MIOs,
agencies…) · **hoi4-build-scripting** (scripted blocks, dynamic modifiers, raw-template domains) ·
**hoi4-build-localisation** (the loc model + whole-mod translate) · cross-entity wiring **hoi4-wiring**.

## 2. Transport (use YOUR OWN account token — PAT-first)
- Base URL = your platform instance, from `HOI4_PLATFORM_URL` (env var; never hard-code).
- **Auth = a personal access token** you generate under **Settings → Access tokens**, read from
  `HOI4_PLATFORM_TOKEN`. Send it on every call as `Authorization: Bearer <token>`. No password ever
  touches a script; revoke/regenerate the token any time.
- **No CSRF on the JSON API.** Complex effect/event bodies → drive with local Python (`urllib`, no
  `requests` dep needed) so you avoid shell-escaping HOI4 script. Chinese round-trips fine as UTF-8 —
  console mojibake is display-only; **assert bytes equal expected, don't trust the terminal render.**
- 🔴 **Always send a `User-Agent`.** Python's `urllib` defaults to `Python-urllib/3.x`, which the
  platform's CDN blocks as a bot signature — every call comes back **HTTP 403 "error code: 1010"**
  no matter how valid your token is. The snippet below sets one; **keep that line.** (If you see
  1010, this is why — it is not an auth problem.)

```python
import json, os, urllib.request, urllib.error
BASE  = os.environ["HOI4_PLATFORM_URL"].rstrip("/")
TOKEN = os.environ["HOI4_PLATFORM_TOKEN"]
def call(m, p, body=None):
    d = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + p, data=d, method=m)
    r.add_header("Content-Type", "application/json")
    r.add_header("Authorization", "Bearer " + TOKEN)
    r.add_header("User-Agent", "hoi4-modmaking-skills/1.x")  # required: bare urllib UA → 403 (1010)
    try:
        x = urllib.request.urlopen(r, timeout=60)
        s = x.read().decode(); return x.status, (json.loads(s) if s else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
```

## 3. Route table (all under `/api/projects/{pid}`)
| Workbench | Resource path | Nested / notes |
|---|---|---|
| Project meta | `GET /api/projects/{pid}` | holds `ideology_registry`, `country_tag(s)`, `dependencies`, `supported_version`, `export_languages` |
| Countries | `/countries` | `ideology` = the **GROUP** (neutrality/democratic/…) not subtype. ⚠️ a custom TAG must not collide with a vanilla country tag (see idiom below) |
| Focus trees | `/focus-trees` | **nodes nested**: `POST/PUT/DELETE /focus-trees/{tree_id}/nodes[/{node_id}]` ; node icon `POST .../nodes/{id}/upload-icon` |
| Events | `/events` | **namespaces nested**: `GET/POST/PUT /events/namespaces[/{ns_id}]` (NOT `/event-namespaces`). picture `POST /events/{id}/upload-picture` |
| Super-events | `/super-events` | no single-GET (405) → read via list. ⚠️ **list GET returns a WRAPPED object `{"super_events":[…]}`** — unwrap the key or a naive `len(list)` reads 0 (false "empty") |
| Decisions | `/decisions` | **categories nested**: `/decisions/categories` |
| Ideas (spirits) | `/ideas` | national spirits live here. icon `POST /ideas/{id}/upload-picture` (multipart) |
| Characters | `/characters` | single `role_type` per char (country_leader / general / …). portrait `POST /characters/{id}/upload-portrait` |
| Dynamic modifiers | `/dynamic-modifiers` | named stat-modifier bundle; `modifier` is a **dict** |
| Opinion modifiers | `/opinion-modifiers` | reusable `add_opinion_modifier` definitions, per country; PUT is field-by-field, `null` deletes a key — see field-reference |
| Modifier definitions | `/modifier-definitions` | custom `modifier@<id>` variable + display formatting (not a stat bundle) — see field-reference |
| Scripted snippets | `/scripted-snippets` | reusable `scripted_effect`/`scripted_trigger` by name (`kind` + `body`) |
| Scripted localisations | `/scripted-localisations` | dynamic `defined_text` loc dispatch (`name` + `body`) |
| Bookmarks | `/bookmarks` | the `effect` block runs **after history, before country-selection** → put `TAG = { promote_character/set_politics }` there to fix the select-screen leader when you flip regime on startup |
| Technologies | `/technologies` | ⚠️ **not recommended — custom techs don't render in-game** (see field-reference). modifier needs `{"__modifier":"<raw flat>"}` · folder = British `armour_folder` · set `name=<tech_id>` |
| Custom traits | `/custom-traits` | country_leader traits |
| States | `/states` | form-level (no province/border editing) |
| History files | `/history-files` | one per country · day-0 start state (politics, ideology split, diplomacy, OOB) — see field-reference |
| Wargoals | `/wargoals` | custom casus-belli / war-goal types; `allowed`/`available`/`take_states`/`puppet`/`liberate` are raw trigger blocks — see field-reference |
| MIOs / Doctrines / Intel | `/mios` · `/doctrines` · `/intelligence-agencies` | ⚠️ **all three list GETs return WRAPPED objects** (`{"mios":[…]}` / `{"agencies":[…],"total":N}`) — unwrap or `len()` reads 0 |
| Equipment | `/equipment` | list GET = bare array; also `/import` + `/preview/{id}` |
| Sub-units | `/sub-units` | custom battalion / company types (`common/units/*.txt`); CRUD + `/import` + `/preview/{id}` |
| Division templates | `/division-templates` | list GET = bare array; also `/import` + `/preview/{id}` |
| Division deployments | `/division-deployments` | place a template at a province (`division_template` = name ref, same `oob_file`) |
| OOB units (air/naval) | `/oob-units/…` | nested CRUD: `/air-wing-groups` · `/air-wings` · `/fleets` · `/task-forces` · `/ships`, plus `/snapshot` (whole-picture read) + `/import` + `/preview` — the air & naval half of the starting OOB |
| Special projects | `/special-projects` | ⚠️ **not recommended — exports can fail to parse** (see field-reference). **nested**: `/specializations` + `/projects` + `/validate` (Götterdämmerung DLC) |
| Autonomy states | `/autonomy-states` | subject/autonomy levels — list GET returns a **wrapped** object `{"autonomy_states":[…]}` (Together for Victory) |
| UI panels | `/ui-panels` | ⚠️ **beta — no build card.** scripted_gui panels; `GET /ui-panels/{id}/files` = the compiled `.gui`/`.txt`/loc. The workbench (and the GUI editor) is still maturing — prefer the other workbenches for production content |
| Whole-mod translate | `GET /translate/languages` · `POST /translate/run` | AI batch-translate of every loc field in the project (daily quota; BYOK supported) — see **hoi4-build-localisation** |
| Relations (read) | `/relations/graph` · `/relations/entity/{kind}/{id}` | read-only cross-ref graph — `resolved:false` = a dangling ref the export would drop |
| Scripted symbols (read) | `/scripted-symbols` | read-only symbol index (used-but-undefined + name collisions) |
| Export | `GET /api/projects/{pid}/export/download` | → zip bytes. `?include_imported=true` to keep imported-origin entities |
| Validate | `POST /api/projects/{pid}/export/validate` · `GET /api/lint/tree-validation/{pid}` | run BOTH before the in-game pass (see §5) |

Ideology sub-ideologies: managed on the **project** (`ideology_registry`), not a standalone route — GET
the project to see/confirm; for a standalone project, fill `ideology_registry.sub_ideologies` with
`{id, group, name:{en,zh}, desc:{en,zh}}` and the export emits the ideology definitions + loc for you.

## 4. Idioms a GET won't reveal (the real value)
- **Effect / trigger / condition fields hold RAW inner HOI4 script text; the export WRAPS them.** You
  store `add_to_variable = { x = 5 }` in the `completion_reward` field; export emits
  `completion_reward = { add_to_variable = { x = 5 } }`. This applies to every "raw-script" field —
  the full list + which fields per workbench is in `field-reference/_raw-script-fields.md`. Write the
  inner text exactly as HOI4 wants; the platform lint (§5) checks a curated set of token-legality, and
  the in-game `error.log` is the final gate.
  - Traps that pass lint but fail in-game: **`research_bonus = {...}` is NOT a valid focus
    completion_reward effect** (it's an idea-definition block; for a one-shot research boost use
    `add_tech_bonus = { bonus = N uses = N category = <cat> }`); **`add_tech_bonus` category must be a
    real tech category** — `construction`/`infrastructure` are NOT categories (use `industry`).
- **Focus `prerequisites` = `list[list[str]]`** (outer = AND, each inner = OR-group): `[["a"]]` = needs
  a; `[["a","b"]]` = needs a OR b. **`mutually_exclusive` = `list[str]`** of focus_ids (list the others
  on each branch-entry node). **Double-POSTing focus nodes silently creates stacked `<focus_id>_1`
  duplicates** — if a tree build re-runs, DELETE the orphan `_1` set.
- **Focus-tree layout is LEFT-anchored** — the left ornamental panel overlaps low-x focuses. Shift every
  node's x right so the minimum x ≈ 4 (PUT each node `{"x": x+shift}`; pure visual).
- **Loc is derived — fill BOTH languages:**
  - Focus: `name_en`/`name_zh` → key `<focus_id>`; `desc_en`/`desc_zh` → key `<focus_id>_desc`.
  - Event: `title_en`/`title_zh`/`desc_en`/`desc_zh` → export auto-emits `title = <event_id>.t` /
    `desc = <event_id>.d` + the loc lines.
  - Event **option** dict keys: `name` = the loc KEY (use `<event_id>.<a|b|c>`; auto if blank), plus
    `name_en`/`name_zh` for the button text; `effects`, `trigger`, `hidden_effects`, `ai_chance`
    (`{"base":N}`). Avoid keying a 4th option `<id>.d` — it collides with the auto desc key.
- **HOI4 decisions/categories are GLOBAL by default — `scope_kind="own"` + `country_tag` does NOT
  restrict in-game visibility.** Those fields only organize which file the decision lands in. To actually
  restrict it, set the decision's `allowed = "original_tag = <TAG>"` (and the category's
  `visible = "original_tag = <TAG>"`).
- **One active `country_leader` per ideology.** A 2nd same-ideology country_leader char is a dormant
  duplicate, not a successor. Succession is event-driven (`kill_country_leader = yes` +
  `create_country_leader = { … }`).
- **A person who is BOTH a commander AND an advisor = ONE character with two role blocks.** Set
  `role_type=general` + `has_advisor_role=True` + `advisor_slot=<slot>` + advisor traits. Two separate
  chars with the same display name → the same person appears twice in-game.
- **A custom country TAG must NOT collide with a vanilla tag** — else `owner=<TAG>` binds to the existing
  vanilla country. Chinese-pinyin 3-letter tags collide a lot (`CHI`=China, `HUN`=Hungary, `SHX`=Shanxi,
  …). Confirm the tag is free before POSTing a new country.
- **Ideas/spirits ship with NO `picture` → the spirit slot shows a "?" placeholder.** PUT
  `picture = "<name>"` where the vanilla sprite is `GFX_idea_<name>` — **the value DROPS the `GFX_idea_`
  prefix** (e.g. `picture = generic_build_infrastructure`). Reuse a vanilla `GFX_idea_*` or upload your
  own via the idea's `upload-picture`.
- **`add_to_variable` / `set_variable` / `set_country_flag` have NO auto-tooltip** — a focus/decision
  whose only reward is a variable change shows an empty effect box. Fill `effect_tooltip_locs`
  (focus/decision) — the export injects `custom_effect_tooltip = <id>_et_tt` + the loc for you.
- **The export GATES cross-refs** — a typo'd `country_event = { id = … }` / focus ref is silently
  dropped. Run validate (§5) so you catch it before the game does.

## 5. Verify through the platform, then in your own game
1. `POST /api/projects/{pid}/export/validate` — cross-refs closed, loc complete in BOTH languages,
   assets shipped.
2. `GET /api/lint/tree-validation/{pid}` — token-legality + structure.
3. Fix everything they flag, then `GET .../export/download`, load the ZIP in your own HOI4, and read
   `logs/error.log` — the final gate for tokens the lint can't know about.

## 6. When a POST 422s / a field is unexpected
GET an existing entity of that type first (#1) and copy its shape. The field meanings + platform quirks
are in `field-reference/<workbench>.md`; the raw-script field list is in
`field-reference/_raw-script-fields.md`.

## Cross-links
- Build workflow + additive-submod rules → **hoi4-submod**.
- End-to-end mod orchestration → **hoi4-mod-design**.
- Authenticate with YOUR OWN token (`Authorization: Bearer`, from `HOI4_PLATFORM_TOKEN`). Never share it.
- Validate on the platform (§5); the in-game `error.log` is the final gate → **hoi4-investigate**.
