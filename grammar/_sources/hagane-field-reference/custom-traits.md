# Custom-trait fields — `/custom-traits`

Author a custom leader/commander/scientist trait = a **modifier bundle** + AI weight + optional icon,
scoped to a project country. Characters then reference the trait token in their `traits` /
`advisor_traits`.

| Field | Meaning |
|---|---|
| `trait_type` | `country_leader` / `unit_leader` / `scientist` (server-validated) |
| `trait_id` | the HOI4 trait token string (unique per project + type; trimmed; empty rejected) |
| `country_tag` | owner (blank = the project's country); stored UPPERCASE |
| `modifier` | **dict** `{stat: value}` — the trait's leader/character modifiers |
| `targeted_modifier` | `list[dict]` of `{tag, modifier}` repeatable blocks |
| `ai_will_do` | raw AI-weight script (`factor = 1 modifier = { … }`) for random assignment |
| `random` | bool — eligible for random assignment |
| `extra_fields` | dict passthrough for arbitrary extra trait keys |
| `name_en` / `name_zh` / `desc_*` | loc (name defaults to the cleaned `trait_id` if blank) |

Modifier fields → `_raw-script-fields.md`; modifier stats → `tokens.md`.

### Sub-resources
- `GET /custom-traits/known` — vanilla-trait DB ∪ project-custom, for the character workbench autocomplete.
- `POST /custom-traits/{trait_id}/upload-icon` — icon (unit_leader / scientist only; a country_leader's
  "icon" is a numeric advisor sprite index, not a custom GFX).

### Common quirks
- **`modifier` is a dict** here (like ideas), NOT a raw flat string (unlike decisions/tech).
- The route `{trait_id}` path param is the **integer DB id**; the `trait_id` in the body is the **string
  token** — don't conflate them.
- Trait tokens are validated by the platform / your in-game `error.log` — POST and check.
