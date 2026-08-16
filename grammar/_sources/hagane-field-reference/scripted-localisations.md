# Scripted-localisation fields — `/scripted-localisations`

A scripted localisation = a HOI4 `defined_text` block: a **dynamic loc key** that resolves to different
text based on triggers (e.g. a title that changes with the country's ideology). Referenced by name in
other loc strings via `[GetName]`-style calls.

| Field | Meaning |
|---|---|
| `name` | the `defined_text` dispatch symbol (unique per project; the list label + uniqueness key) |
| `body` | **raw HOI4 script** — the verbatim inner content of the `defined_text` block (it re-includes the `name = X` line itself) |
| `source_file` | target `common/scripted_localisation/*.txt` filename |

`body` is a raw HOI4 `defined_text` block (not an effect/trigger/modifier) — write it as HOI4 spells it;
the platform validates on export.

### Common quirks
- `name` is an **internal dispatch symbol**, not player-facing text — the actual displayed strings live
  in the referenced localisation entries.
- No `kind` discriminator (unlike scripted-snippets) — one entity type.
- Duplicate `name` is a 409.
- source_file is a complete mod-relative path under common/scripted_localisation/, not a bare filename.
