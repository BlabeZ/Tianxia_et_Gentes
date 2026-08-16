# Intelligence-agency fields — `/intelligence-agencies`

Author a country's spy-agency identity: name pool, logo, availability, and upgrade-branch tree.
**DLC: La Résistance** — only applies for players who own that DLC.

| Field | Meaning |
|---|---|
| `agency_id` | stable script token (unique per project, e.g. `usa_oss`) |
| `country_tag` | owning country |
| `picture` | GFX sprite for the logo (auto-written by `upload-logo`) |
| `names` | `list[str]` of candidate agency names — the engine picks one at random |
| `default_trigger` | **raw trigger** — which country gets this agency by default |
| `available` | **raw trigger** — availability gate |
| `upgrade_branches` | `list[dict]` — the upgrade tree (round-trips as raw branch dicts) |
| `scope_kind` | `own` / shared (default `own`) |
| `shared_country_tags` | tags sharing this agency when shared |

Raw-script trigger fields → `_raw-script-fields.md`.

### Sub-resources
- `POST /intelligence-agencies/{id}/upload-logo` — the agency logo (upload; a base-sprite ref won't ship).

### Common quirks
- `names` is a `list[str]` — the engine picks a name at random from the pool.
- The route `{agency_db_id}` path param is the **integer DB id**, not the `agency_id` string.
- No description fields — the agency has no desc slot.
- agency_id is not a block identifier; when names is empty, export uses agency_id as the sole names token and localisation key.
