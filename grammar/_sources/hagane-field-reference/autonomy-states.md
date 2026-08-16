# Autonomy-state fields — `/autonomy-states`

Author subject/autonomy levels (the puppet-rule + modifier bundle that binds a subject to an overlord).
**DLC: Together for Victory** (the subject/autonomy system) — only applies for players who own it.

| Field | Meaning |
|---|---|
| `autonomy_id` | string script id of the autonomy level (auto-suffixed on collision) |
| `country_tag` | owning country (uppercased) |
| `is_puppet` | bool — this level is a puppet subject |
| `is_default` | bool — this is the default autonomy level |
| `manpower_influence` | float — manpower influence at this level (nullable) |
| `min_freedom_level` | **int stored as freedom × 1000** (the export restores the decimal) |
| `rule` | **raw autonomy-rule block** (`can_be_target` / `can_take_level` / …) |
| `ai_weights` | dict — AI weighting factors for picking this level |
| `modifier` | **dict** `{stat: value}` — country modifiers applied at this level |

Raw-script + modifier fields → `_raw-script-fields.md`; modifier stats → `tokens.md`.

### Common quirks
- `modifier` is a **dict** (like ideas), not a raw flat string.
- `min_freedom_level` is stored as an **integer = freedom × 1000** (e.g. freedom 0.25 → `250`); the export
  divides it back.
- The route `{autonomy_db_id}` path param is the **integer DB id**, not the `autonomy_id` string.
- ai_weights maps each HOI4 weight key to RAW inner script text, for example {'ai_subject_wants_higher': 'factor = 1.0'}.
