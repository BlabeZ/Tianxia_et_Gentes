# Doctrine fields — `/doctrines`

Author the modern doctrine system. It's **one discriminated table** — the `entity_type` field says which
of four kinds each row is; they nest by string key, not by FK.

| Field | Meaning |
|---|---|
| `entity_type` | the discriminator: `folder` / `grand_doctrine` / `track` / `subdoctrine` (default `grand_doctrine`) |
| `entity_key` | required unique key within `(project, entity_type)` (e.g. `land`, `new_mobile_warfare`) |
| `folder_key` | parent doctrine folder this entity belongs to (**string key**, not an int FK) |
| `track_key` | parent track this entity belongs to (**string key**, not an int FK) |
| `icon` | GFX sprite for the node |
| `xp_cost` | experience points to unlock the node |
| `xp_type` | which XP pool the cost draws from (`army` / `navy` / `air`) |
| `xor` | 1.19+ · subdoctrine only · **raw inner list** of subdoctrine keys that can't be active in another track of the same folder (send `"other_sub_a other_sub_b"`; the export wraps it as `xor = { … }`) |
| `allow_in_multiple_tracks` | 1.19+ · subdoctrine only · `true` → assignable to multiple tracks at once (omit = vanilla default no) |
| `source_file` | which output file this entity emits into |
| `raw_extras` | the node's **modifier / milestones / rewards / mastery blocks** live here (see note) |

### ⚠️ No typed modifier field — it rides in `raw_extras`
Unlike other workbenches, a doctrine node's actual bonus content (modifier / milestones / rewards /
mastery) is not a typed field — it round-trips through `raw_extras`. This makes doctrines an **advanced
workbench**: build the hierarchy (folder → grand_doctrine → track → subdoctrine) with the typed fields
above, and carry the bonus blocks in `raw_extras`. GET an existing doctrine node to see the exact
`raw_extras` shape before authoring one.

### Common quirks
- The hierarchy is expressed only through `entity_type` + `folder_key`/`track_key` strings — there are no
  nested sub-routes.
- Routes are keyed by the **integer DB id**, not `entity_key`.
- `(project, entity_type, entity_key)` is unique → 409 on conflict.
- `xor` / `allow_in_multiple_tracks` emit **only** while `entity_type` is `subdoctrine`. Switching a
  subdoctrine to another type keeps the stored values but stops emitting them (switch back to restore).
- source_file is relative to common/doctrines/ (for example folders/my_doctrines.txt), not a mod-relative path.
