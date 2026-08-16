# Country fields — `/countries`

Country rows are the **scope anchor** — every other workbench references a country by its `tag`. Create
these first. (Reusing a vanilla TAG is allowed — that's the "replace a vanilla country" pattern.)

| Field | Meaning |
|---|---|
| `tag` | country TAG — regex `^[A-Z][A-Z0-9]{1,4}$` (2–5 chars, must start with a letter). The id everything scopes to |
| `name` | display name (auto-split into en/zh if you don't give `name_en`/`name_zh`) |
| `color` | map/country color as `[r, g, b]` |
| `color_ui` | optional HOI4 `color_ui` override; **empty list = fall back to `color`** (sending `[]` clears an override, it's not a no-op) |
| `ideology` | default ruling ideology GROUP (default `neutrality`) |
| `graphical_culture` / `graphical_culture_2d` | art set; blank = per-tag vanilla resolution at export |
| `flag_image_path` | relative path to a `.tga` flag → shipped as `gfx/flags/<TAG>.tga` (or upload via `{id}/upload-flag`) |
| `name_neutrality` / `name_democratic` / `name_communism` / `name_fascism` (+ `*_zh`) | per-ideology display-name overrides (the country's name under each government) |
| `use_legacy_ai_pp_spend` | optional bool; unset = export omits it |

No raw-script fields — countries are pure identity/metadata.

### Sub-resources
- `GET /countries/grouped` — authored vs imported-reference split with per-workbench content badges.
- `GET /countries/{id}/delete-preview` — dry-run cascade-delete counts before you delete.
- `POST /countries/{id}/upload-flag` — flag upload (resized 82×52 → .png + .tga).

### Common quirks
- **A custom TAG must not accidentally collide with a vanilla tag** unless you intend to replace that
  country — the platform allows it (soft warning) because "replace vanilla" is a real pattern.
- `ideology` here is the **GROUP** (neutrality/democratic/communism/fascism), not a sub-ideology.
- Changing `tag` via PUT fires a rename cascade across every entity that referenced it — expected.
