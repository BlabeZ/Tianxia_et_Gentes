# Ideology fields — project `ideology_registry`

Ideologies are not a standalone workbench route — the vocabulary lives on the **project**:
`GET /api/projects/{pid}` → `ideology_registry`, updated via `PUT /api/projects/{pid}`. Every
sub-ideology dropdown/field (characters, countries, bookmarks) reads from it.

| Field | Meaning |
|---|---|
| `ideology_registry.groups` | effective GROUP vocabulary. Custom root ids are derived automatically from `root_definitions` |
| `ideology_registry.root_definitions` | standalone-only expert definitions: `{id, body, name:{en,zh}, desc:{en,zh}}`; `body` is the ordered inner group script and must contain `types` and `color` blocks |
| `ideology_registry.sub_ideologies` | `list[dict]` of `{id, group, name:{en,zh}, desc:{en,zh}}` — your custom sub-ideologies |

The effective vocabulary = **vanilla base ∪ your registry**, add-only: vanilla's 4 groups + 22
sub-ideologies are always available, and a registry entry reusing a vanilla id overrides only its
display name. You list your additions; you never re-list vanilla. A standalone project may also
define a new root group, while a submod must inherit root groups from its base mod.

```
PUT /api/projects/{pid}
{"ideology_registry": {"sub_ideologies": [
  {"id": "junzheng", "group": "neutrality",
   "name": {"en": "Military Government", "zh": "军政"},
   "desc": {"en": "…", "zh": "…"}}]}}
```

Expert standalone ROOT example (the platform supplies `ideologies = { ... }` and the outer ROOT
braces; never put them in `body`):

```
PUT /api/projects/{pid}
{"ideology_registry": {
  "root_definitions": [{
    "id": "market_socialism",
    "name": {"en": "Market Socialism", "zh": "市场社会主义"},
    "body": "types = {\n}\ncolor = { 128 32 32 }\nrules = { can_force_government = yes }"
  }],
  "sub_ideologies": [{"id": "syndicalism", "group": "market_socialism"}]
}}
```

## What the export does for you (standalone project)
Define custom roots/subtypes in the registry, put them on a character/country, and the export:
1. emits a **complete `common/ideologies/00_ideologies.txt`** — all 4 vanilla groups verbatim, with
   your new roots appended and custom subtypes spliced into their target group's `types`;
2. auto-adds **`replace_path="common/ideologies"`** to the descriptor (outer + inner `.mod`, always
   strictly consistent with the emitted file);
3. emits root and subtype loc: `<id>` (the name) + `<id>_desc`.

You hand-write nothing. The full-file + replace_path shape is the ONLY legal way to add a subtype to an
existing group (failure mode below) — which is why the platform owns it.

- **Submods**: auto-emit is skipped and custom `root_definitions` are rejected — the base mod's
  ideology space is inherited. Read it via `GET .../import/basemod-index/ideology-registry` and
  reference its ids directly.
- **Raw precedence**: if you ship any raw file under `common/ideologies/`, the auto-emit steps aside
  (two files defining the same groups would collide) — your raw file must then be the complete thing.

## 🚩 The fatal failure mode: a second `<group> = { }` block
Hand-writing a raw fragment that re-opens an existing group to add a subtype —

```
ideologies = {
    neutrality = {                      # ← vanilla already defines neutrality
        types = { my_subtype = { } }
    }
}
```

— makes HOI4 raise **`Duplicate database id: <group>`** and **silently discard the entire block**. The
cascade: `<my_subtype> is not a valid ideology` → `No political party for country leader …` → the
leader fails to load and the country shows **no leader** (无指挥官). One malformed block, three
misleading errors. Full-group copies and "additive" `types`-only fragments collide the same way.

Correct paths — pick ONE:
1. **Platform registry** (above) — the automatic full-file + replace_path. Default choice.
2. **Raw full replacement** — ship the COMPLETE ideologies file at `common/ideologies/…` with
   `generate_replace_path: true`. Use this only for advanced shapes the ordered ROOT body cannot
   represent or when you intentionally take ownership of every definition in the directory.

Cheap third option when all you need is a NAME: keep a vanilla subtype (e.g. `despotism`) and
loc-rename it — ⚠️ the rename is GLOBAL (every country of that subtype shows your name).

## Where the name actually shows in-game
- Politics screen `Ideology` field = the **GROUP** name; `Government` = `<group>_desc`. A custom
  sub-ideology does NOT change these.
- The sub-ideology's own name/desc show on **hover of the leader's ideology icon**.
- To surface custom naming in the ruling-party field:
  `set_party_name = { ideology = <group> name = <LOC_KEY> long_name = <LOC_KEY> }` in a history/effect
  field — it takes loc KEYS, not literals.

## Group / subtype key quick-ref (raw full-replacement writers only)
Wiki-common keys — 以游戏实装为准: verify against your game's `common/ideologies/00_ideologies.txt`.
- **Group**: `types = { … }` · `color = { r g b }` · `rules = { can_force_government / can_puppet /
  can_send_volunteers / can_lower_tension / can_guarantee_other_ideologies /
  can_create_collaboration_government / … }` · `war_impact_on_world_tension` /
  `faction_impact_on_world_tension` · `modifiers = { generate_wargoal_tension / join_faction_tension /
  lend_lease_tension / guarantee_tension / … }` · `faction_modifiers = { faction_trade_opinion_factor }`
  · `dynamic_faction_names` · `can_host_government_in_exile` · `can_collaborate` · `can_be_boosted`
  (wiki-documented, default yes) · `ai_democratic` / `ai_communist` / `ai_fascist` / `ai_neutral` ·
  `ai_ideology_wanted_units_factor`
- **Subtype**: usually `{ }` empty; `can_be_randomly_selected = no` = never assigned to randomly
  generated leaders.
