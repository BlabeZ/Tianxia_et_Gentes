# Scripted-snippet fields — `/scripted-snippets`

A scripted snippet = a **reusable named `scripted_effect` or `scripted_trigger` block** you call by name
from other entities' effect/trigger fields. Define once, reference everywhere.

| Field | Meaning |
|---|---|
| `kind` | `effect` or `trigger` — picks `scripted_effects` vs `scripted_triggers` (default `effect`) |
| `name` | the dispatch symbol other entities call by name (unique per project + kind) |
| `body` | **raw HOI4 script** — the verbatim content inside the block braces (an effect body when `kind=effect`, a trigger body when `kind=trigger`) |
| `source_file` | target `common/scripted_effects\|triggers/*.txt` filename |

Raw-script: `body` (effect or trigger per `kind`) → tokens in `tokens.md`.

### Common quirks
- `name` is an **internal dispatch symbol**, not player-facing text — no loc fields.
- Call it from another entity's effect field with `<name> = yes` (effect) or in a trigger with `<name> = yes`.
- Duplicate `(kind, name)` is a 409.
- source_file is a complete mod-relative path under common/scripted_effects/ or common/scripted_triggers/, not a bare filename.
