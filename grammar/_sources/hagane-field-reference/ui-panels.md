# UI-panel fields — `/ui-panels` (界面机制 Builder)

Author a `scripted_gui` interface panel — a window + its controls (text / buttons / icons). You fill
structured fields; **the platform compiles them into the `.gui` window, the `scripted_gui` `.txt`, and the
merged localisation** (preview == export). You never write GUI markup — that's exactly what this
workbench replaces.

## Panel (`POST /api/projects/{pid}/ui-panels`)
| Field | Meaning |
|---|---|
| `token` | **required** snake_case naming seed (e.g. `mymod_stability`) — the sole input that derives every window/gui/loc name. Auto-suffixed on collision |
| `country_tag` | owner scope (uppercased) |
| `context_type` | the scripted_gui context — one of: `player_context` · `selected_country_context` · `selected_state_context` · `decision_category` · `diplomatic_action` · `national_focus_context` · `country_mapicon` · `state_mapicon` (default `decision_category`; an invalid value is a 422) |
| `parent_window_token` | token of a parent window to nest under (a token ref, not an FK) |
| `visible_trigger` | **raw trigger** — gates whether the whole window shows |
| `window_props` | dict of window geometry `{x, y, width, height}` |
| `controls` | `list[dict]` — the panel body (see control shapes below) |
| `name_en` / `name_zh` / `display_name_locs` | window title loc |

`visible_trigger` → `_raw-script-fields.md`; trigger tokens → `tokens.md`.

## Control shapes (each dict in `controls`)
Every control has a `kind`; the other keys depend on it.

| `kind` | Keys |
|---|---|
| `text` | `text` (the string → becomes a loc key; supports `[?var\|fmt]` runtime tokens), `font`, `format` (`left`/`right`/`center`), `x`/`y`/`width`/`height` |
| `button` | `sprite` (button GFX), `text` (button label), `click_effect` (**raw effect** run on click), `click_enabled_trigger` (**raw trigger** gating clickability), `visible` (**raw trigger** per-control), `font`, tooltip, `x`/`y` |
| `icon` / `progressbar` | `sprite` (GFX), `frame` (default 1), `x`/`y` |

The button's `click_effect` / `click_enabled_trigger` / `visible` hold raw HOI4 script — the platform
wraps them into the scripted_gui's `effects` / `triggers` blocks for you.

## Sub-resource
- `GET /ui-panels/{panel_db_id}/files` — the **compiled** `.gui` text + `.txt` text + per-language loc.
  This is byte-identical to what the export ships (preview == export) — use it to eyeball the result.

### Common quirks
- **`width`/`height` on a control are canvas-preview only for buttons.** The platform deliberately omits
  the button size block from the emitted GUI — writing a `size = { … }` on a HOI4 `buttonType` crashes the
  parser and the button renders but can't be clicked. The platform handles this correctly; you just fill
  w/h for your own preview.
- An empty button `sprite` falls back to a default visible sprite (an invisible-but-clickable button is a
  trap the platform avoids by construction).
- `token` is the naming seed — renaming it re-derives every name; the platform cleans up the old snapshot.
- Save is a live compile: after POST/PUT, GET `/files` to see the exact compiled output.
