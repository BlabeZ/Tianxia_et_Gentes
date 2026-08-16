# OOB-unit fields — `/oob-units`

Structured **air wings and navy** for a country's starting order of battle. Five nested collections
under one workbench, plus snapshot / preview / import. Everything shares the `oob_file` group with
division-templates / division-deployments — one starting-OOB file per `oob_file`.

Hierarchy (parents by **integer DB id FK**, unlike division-deployments' name ref):

- `air-wing-groups` (one per air base) → `air-wings` (via `group_id`)
- `fleets` → `task-forces` (via `fleet_id`) → `ships` (via `task_force_id`)

## Routes
- `GET /oob-units/snapshot` (`?oob_file=` / `?source_file=`) → ONE object
  `{"air_wing_groups":[…],"air_wings":[…],"fleets":[…],"task_forces":[…],"ships":[…]}`
- `GET /oob-units/preview` (`?oob_file=` / `?source_file=`) → `{"script": …}` — the generated
  air-wings + fleet blocks; 422 if a stored token can't render.
- `POST /oob-units/import` — `{oob_file, source_file, country_tag, text, policy}` (`overwrite`/`skip`);
  parses a whole OOB file body into the five collections.
- Full CRUD per collection: `GET`(list)/`POST` on `/air-wing-groups` (`?oob_file=`), `/air-wings`
  (`?group_id=`), `/fleets` (`?oob_file=`), `/task-forces` (`?fleet_id=`), `/ships`
  (`?task_force_id=`); `GET`/`PUT`/`DELETE` on `…/{id}`. List GETs are bare arrays; PUT is partial.

## Air-wing-group fields
| Field | Meaning |
|---|---|
| `oob_file` | OOB group stem (shared with division-templates/deployments) |
| `country_tag` | owning country (uppercased) |
| `location` | **required on create** — the **state id** of the air base; becomes the block key inside `air_wings = { … }` |
| `ordering` | sort order (default 0) |
| `layout` / `source_file` | import-preservation (see quirks) |

## Air-wing fields
| Field | Meaning |
|---|---|
| `group_id` | int FK → an air-wing-group in the same project (404 if missing) |
| `equipment_type` | **required** — the plane equipment token; becomes the wing's block key |
| `amount` | number of planes (string token) |
| `owner` | country tag providing the planes (string token) |
| `name` | wing display name (quoted on emit) |
| `ordering` / `body_ast` | sort order / import-preservation |

## Fleet fields
| Field | Meaning |
|---|---|
| `oob_file` / `country_tag` | as above |
| `name` | fleet display name (quoted) |
| `naval_base` | **province id** of the home naval base (string token) |
| `ordering` / `layout` / `source_file` | sort / import-preservation |

## Task-force fields
| Field | Meaning |
|---|---|
| `fleet_id` | int FK → a fleet in the same project |
| `name` | task-force display name (quoted) |
| `location` | **province id** where the task force starts (string token) |
| `ordering` / `layout` | sort / import-preservation |

## Ship fields
| Field | Meaning |
|---|---|
| `task_force_id` | int FK → a task force in the same project |
| `name` | ship name (quoted) |
| `definition` | ship type token (e.g. `destroyer`, `carrier`) |
| `equipment_type` | the hull/equipment token — with `amount` / `owner` / `version_name` it composes the ship's `equipment = { <type> = { … } }` block |
| `amount` | usually `"1"` (string token) |
| `owner` | country tag (string token) |
| `version_name` | the equipment **variant** name this ship uses (quoted; should match a variant you or vanilla defined) |
| `start_experience_factor` | starting XP (string token, e.g. `"0.25"`) |
| `ordering` / `body_ast` | sort / import-preservation |

### Common quirks
- 🔴 **Scalar fields are strings even when numeric** (`location`, `amount`, `naval_base`,
  `start_experience_factor`, …) — send `"9601"`, not `9601`. They are validated as HOI4 script
  tokens on write; an invalid token is a 422. An **empty string omits the line entirely**.
- Parent links are **integer DB-id FKs** (`group_id` / `fleet_id` / `task_force_id`), checked against
  the same project — the opposite idiom from division-deployments' name ref. Create parents first.
- `layout` / `body_ast` exist to preserve an imported file's exact line order and unmodeled keys.
  **When authoring fresh, leave them empty** — children then emit in `ordering` order. Layout entries
  address children by their `ordering` ordinal, so keep `ordering` unique among siblings.
- Export merges everything sharing one `oob_file` into a single starting-OOB file: division
  templates first, then the `air_wings = { … }` block, then one `units = { … }` block holding both
  division deployments and fleets. The country's history file must reference that OOB stem
  (`oob = "<stem>"`) — see **hoi4-build-scenario**.
- Air-base states and naval-base/task-force provinces must actually exist (and the naval base be
  built) — states are edit-only on the platform (seed from vanilla first).
- Use `GET /oob-units/preview` after building and proofread the script before export.

### Minimal example (one destroyer flotilla)
```
POST /oob-units/fleets        {"oob_file": "MOD_1936", "country_tag": "MOD",
                               "name": "1st Fleet", "naval_base": "9601"}
POST /oob-units/task-forces   {"fleet_id": <fleet id>, "name": "1st Destroyer Flotilla",
                               "location": "9601"}
POST /oob-units/ships         {"task_force_id": <tf id>, "name": "MODS Vanguard",
                               "definition": "destroyer", "equipment_type": "destroyer_1",
                               "amount": "1", "owner": "MOD", "version_name": "1936 Destroyer"}
```
