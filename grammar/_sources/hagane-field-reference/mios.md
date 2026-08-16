# MIO fields — `/mios`

Author Military Industrial Organizations (manufacturer companies with trait trees).
**DLC: Trial of Allegiance** — these only apply for players who own that DLC.

| Field | Meaning |
|---|---|
| `mio_id` | unique MIO script id (e.g. `USA_marmon_herrington_organization`) |
| `country_tag` | owning country |
| `include` | path to a vanilla/base MIO template to inherit from |
| `icon` | GFX sprite (idea-namespace `GFX_idea_*`; auto-overwritten by `upload-icon`) |
| `equipment_type` | `list[str]` of equipment archetypes this MIO builds |
| `research_categories` | `list[str]` of research categories the MIO applies to |
| `allowed` | **raw trigger** — static gate for which countries get this MIO |
| `available` | **raw trigger** — runtime availability |
| `visible` | **raw trigger** — visibility |
| `traits` | `list[dict]` of trait entries — each holds nested `modifier` / `equipment_bonus` blocks + optional per-trait icon, keyed by the trait's `token` |
| `scope_kind` | `own` / shared (default `own`) |
| `shared_country_tags` | tags sharing this MIO when `scope_kind` is shared |

Raw-script trigger fields → `_raw-script-fields.md`.

### Sub-resources
- `POST /mios/{id}/upload-icon` + `/mios/{id}/traits/{token}/upload-icon` — MIO + per-trait icons.

### Common quirks
- The route `{mio_db_id}` path param is the **integer DB id**, not the `mio_id` string.
- `traits` entries are plain JSON dicts with **no DB id** — per-trait icons are keyed by the trait's
  `token`, and the whole `traits` list is one JSON column (edit it as a whole).
- `mio_id` collision is a 409.
- name is an optional HOI4 localisation key, not player-facing text; blank uses the engine default <mio_name>_<trait_token>.
