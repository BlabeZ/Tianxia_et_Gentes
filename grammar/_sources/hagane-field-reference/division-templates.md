# Division-template fields — `/division-templates`

Author OOB division templates (line battalions + support companies) for a country's starting army.

| Field | Meaning |
|---|---|
| `oob_file` | which OOB group this template belongs to (a filename stem, e.g. `USA_1936`); also derives `country_tag` |
| `template_name` | division template display name (default `New Division`) |
| `country_tag` | owning country; auto-derived from the `oob_file` prefix if left blank |
| `division_names_group` | naming-list group referenced by the template |
| `regiments` | line battalions — `list[dict]` of `{token, x, y}` (the unit token + its combat-width column/row) |
| `support` | support companies — `list[dict]` of `{token, x, y}` |
| `is_locked` | template locked from in-game player editing (nullable) |
| `priority` | production / reinforcement priority (nullable) |
| `ordering` | sort order within the `oob_file` group (default 0) |

No raw-script fields.

### Common quirks
- `country_tag` is prefix-derived from `oob_file` (split on the first `_`, uppercased) when blank.
- `regiments` / `support` are `list[dict{token, x, y}]` (line battalions vs support companies), stored as
  JSON — not separate rows.
- `oob_file` is shared with the **division-deployments** workbench (same group).
