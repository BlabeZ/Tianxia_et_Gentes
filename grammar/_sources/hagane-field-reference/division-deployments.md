# Division-deployment fields — `/division-deployments`

Place a division template at a province — a country's starting army units. Pairs with
division-templates (same `oob_file` group).

| Field | Meaning |
|---|---|
| `oob_file` | OOB group stem, shared with division-templates |
| `country_tag` | owning country; auto-derived from the `oob_file` prefix if unset |
| `division_template` | **name** reference to a division template's `template_name` (a string, not an FK) |
| `location` | province id where the division spawns (int, nullable) |
| `count` | batch-expand into N identical divisions (default 1) |
| `division_name` | custom in-game name for the placed division |
| `start_experience_factor` | starting XP factor (float, optional) |
| `start_equipment_factor` | starting equipment fill factor (float, optional) |
| `ordering` | sort order within the `oob_file` group (default 0) |

No raw-script fields.

### Common quirks
- `division_template` is a **name string ref** to a `division-templates` `template_name` — create the
  template first, then reference it by name.
- `location` is a bare province id (int), not an entity FK.
- `count` batch-expands into N deployment blocks on export.
