# Equipment fields — `/equipment`

Author army equipment archetypes + concrete variants (combat stats, build cost, resources).

| Field | Meaning |
|---|---|
| `equipment_id` | unique key (default `new_equipment`; auto-suffixed on collision) |
| `country_tag` | owner (uppercased); `""` = global equipment |
| `equipment_type` | HOI4 `type` (`infantry` / `armor` / `artillery` / …) |
| `is_archetype` | bool — this row is an archetype (the parent) vs a concrete variant |
| `archetype` | parent archetype id this variant belongs to (`""` = this row is itself an archetype); **string ref, not an int FK** |
| `parent` | upgrade-chain parent equipment id (string ref) |
| `is_buildable` | Optional bool — `None` = the field is absent (distinct from `false`) |
| `year` | introduction year (optional) |
| `picture` | GFX sprite |
| `build_cost_ic` | IC build cost (optional; `None` = inherited from archetype) |
| `soft_attack` / `hard_attack` / `defense` / `armor_value` / `max_strength` / … | numeric combat stats — **all Optional; `None` = inherited from the archetype, NOT zero** |
| `resources` | dict `{resource: amount}` |
| `can_license` | Optional bool |

No raw-script fields — equipment is numeric/metadata.

### Sub-resources
- `GET /equipment/enabled-by/{equipment_id}` — reverse lookup: which techs unlock this equipment.
- `POST /equipment/import` — import one equipment `.txt` body.

### Common quirks
- **Every stat is Optional; `None` means "inherit from the archetype", not zero.** A variant persists only
  the columns it explicitly overrides — don't send `0` where you mean "inherit".
- `archetype` and `parent` are **string equipment-id references**, not int FKs.
