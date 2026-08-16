# Modifier-definition fields — `/modifier-definitions`

Author custom **modifier variables** (`common/modifier_definitions/*.txt`) — these aren't a bundle of
stat bonuses (that's `dynamic-modifiers.md`); they declare **one named, typed value** that other script
can read back via `modifier@<modifier_id>`, with display formatting (color, decimals, unit suffix) for
wherever the game shows it (`guides/modifiers.md` §Modifier Definitions).

| Field | Meaning |
|---|---|
| `modifier_id` | unique per project. Must match `^[A-Za-z_][A-Za-z0-9_]*$` (letters/digits/underscore, can't start with a digit) — `422` otherwise |
| `color_type` | `good` / `bad` / `neutral` — tooltip color when the value shows. Default `bad` |
| `value_type` | `number` / `percentage` / `percentage_in_hundred` / `yes_no`. Default `number` |
| `precision` | decimal places shown, `0`–`3`. Default `2` |
| `postfix` | `none` / `days` / `hours` / `daily`. Default `none` |
| `categories` | list — limits where the modifier is selectable. **At least one required**; duplicates are silently deduped. Default `["all"]`. Legal values: `none · all · country · state · unit_leader · army · naval · air · peace · politics · ai · defensive · aggressive · war_production · military_advancements · military_equipment · autonomy · government_in_exile · intelligence_agency` — anything else is a `422` |
| `explicit_fields` | 🔴 **read-only** — the platform tracks which of the fields above you've actually set (vs. left at default) so re-editing doesn't clobber untouched ones. Don't try to write it. |

### Common quirks
- `modifier_id` collision (same project) → `409`.
- An unknown `categories` entry, an out-of-range `precision`, or an invalid enum on any of
  `color_type`/`value_type`/`postfix` → `422` with the specific bad value named.
- This only **declares** the modifier variable — nothing sets its value for you. Give it a value with
  `set_variable = { modifier@<modifier_id> = N }` (or similar) from wherever your mod needs it, then
  reference it as `modifier@<modifier_id>` in tooltips/effects.
- Distinct from `dynamic-modifiers.md`: a dynamic modifier is a **named bundle of existing stat
  bonuses** applied to a scope; a modifier definition is a **single custom variable** with its own
  display formatting.
