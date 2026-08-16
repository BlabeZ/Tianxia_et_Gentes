# Sub-unit fields — `/sub-units`

Author battalion / company **unit types** (the building blocks that division templates reference by
token in their `regiments` / `support` grids) — a structured editor over HOI4's unit-definition files.

| Field | Meaning |
|---|---|
| `sub_unit_id` | the unit token (default `new_sub_unit`; auto-suffixed on collision). This is the string a division template's `regiments`/`support` entries reference |
| `country_tag` | organizational owner (uppercased); the emitted unit file itself is mod-wide |
| `source_file` | output-file group (imported rows keep their original path; created rows default to one mod-wide file) |
| `ordering` | sort order within the output file (default 0) |
| `name`, `name_en` / `name_zh`, `display_name_locs` | display-name loc text (plus `desc_en` / `desc_zh` / `description_locs` for descriptions) |
| `abbreviation` | short unit label |
| `sprite` | unit model/sprite token |
| `map_icon_category` | map counter icon category (e.g. `infantry`, `armored`, `ship`) |
| `priority` / `ai_priority` | int — reinforcement / AI priorities (nullable) |
| `transport` | transport equipment archetype (what the unit rides in) |
| `group` | recruitment-tab group the unit appears under |
| `active` | bool — available without a tech unlock (nullable) |
| `cavalry` / `special_forces` / `marines` / `mountaineers` / `can_be_parachuted` / `can_exfiltrate_from_coast` / `affects_speed` | capability flags — **all tri-state** (see quirks) |
| `unit_types` | `list[str]` — emitted as the HOI4 `type = { … }` block (the platform renames the field) |
| `categories` | `list[str]` of unit-category tags |
| `essential` | `list[str]` of essential equipment archetypes |
| `need` | dict `{equipment_archetype: amount}` — the equipment the battalion consumes |
| `stats` | dict — **the catch-all for every root numeric stat** (`maxspeed`, `max_strength`, `max_organisation`, `default_morale`, `combat_width`, `manpower`, `training_time`, `weight`, `supply_consumption`, `suppression`, …). There are no per-stat typed columns |
| `terrain_modifiers` | dict `{terrain: {modifier: value}}` — standard terrain keys only (`forest`, `hills`, `mountain`, `jungle`, `marsh`, `plains`, `urban`, `desert`, `river`, `amphibious`, `fort`, `shore`, `snow`, `ice`) |
| `raw_extras` | import-preserved keys the typed fields don't model — re-emitted on export (a typed field with the same key wins) |

### Sub-resources
- `GET /sub-units/preview/{id}` → `{"script": "<the emitted unit block>"}` — proofread before export.
- `POST /sub-units/import` — body `{text, source_file, policy}`; the text must contain a
  `sub_units = { … }` wrapper; `policy` = `overwrite` (default) or `skip`.

### Common quirks
- The route `{id}` path param is the **integer DB id**, not the `sub_unit_id` string.
- List GET is a bare array; filter with `?country_tag=` and/or `?source_file=`.
- **Tri-state booleans**: `None`/omitted = the line is not emitted at all (engine default applies);
  `False` = an explicit `no`. Don't send `False` when you mean "leave it to the engine".
- `unit_types` ↔ HOI4 `type` — the platform field name differs from the script token.
- Anything structured the typed fields can't hold is preserved into `raw_extras` on import (with a
  warning) and re-emitted verbatim — check `raw_extras` after importing before assuming a field is lost.
- Editing an imported row flips it to created; an untouched imported file group replays its original
  file verbatim on export (comments and all), while any edit promotes the whole group to the
  structured emitter.
- Loc: fill `name_en`/`name_zh` (or `display_name_locs`) and confirm loc coverage with
  `POST /api/projects/{pid}/export/validate` — the unit script itself carries no loc lines.

### Minimal example
```json
{
  "sub_unit_id": "my_assault_infantry",
  "group": "infantry",
  "map_icon_category": "infantry",
  "unit_types": ["infantry"],
  "categories": ["category_front_line", "category_light_infantry", "category_army"],
  "essential": ["infantry_equipment"],
  "need": {"infantry_equipment": 120},
  "stats": {"max_strength": 25, "max_organisation": 60, "default_morale": 0.3,
            "combat_width": 2, "manpower": 1000, "training_time": 90,
            "weight": 0.5, "supply_consumption": 0.06},
  "terrain_modifiers": {"urban": {"attack": 0.1}},
  "active": true,
  "name_en": "Assault Infantry"
}
```
