# Dynamic-modifier fields — `/dynamic-modifiers`

A dynamic modifier = a **named stat-modifier bundle** applied at runtime and gated by triggers. Focuses,
events, and decisions reference it by `dm_id` to add/remove it.

| Field | Meaning |
|---|---|
| `dm_id` | unique string id (trimmed; auto-suffixed on collision) |
| `country_tag` | optional owner (uppercased); `""` = global/unscoped |
| `icon` | GFX sprite shown on the modifier's tooltip |
| `enable` | **raw trigger** — when the modifier is active/applicable |
| `remove_trigger` | **raw trigger** — when true, the modifier auto-removes |
| `modifier` | **dict** `{stat: value}` — the actual stat effects the bundle grants |
| `name_en` / `name_zh` / `desc_*` | loc |

Raw-script fields → `_raw-script-fields.md`; modifier stats → `tokens.md`.

### Common quirks
- **`modifier` is a dict** (like ideas), NOT a raw flat string (unlike decisions).
- `dm_id` colliding with a vanilla dynamic-modifier id emits a warning (warn-and-allow).
- `country_tag` is uppercased on store — pass it uppercase to keep filters consistent.
