# Bookmark fields — `/bookmarks`

A bookmark = a **country-selection scenario** (剧本): the screen where the player picks a nation at a
start date. Name/desc/date/backdrop + which countries are playable with per-country hover blurbs.

| Field | Meaning |
|---|---|
| `bookmark_id` | unique script token / scenario id (required, trimmed) |
| `date` | scenario start date (default `1936.1.1.12`) |
| `picture` | GFX sprite for the backdrop (default `GFX_select_date_1936`; or upload via `{bm_id}/upload-picture`) |
| `default_country` | pre-selected country tag on the screen |
| `default_flag` | bool — is this the default/highlighted bookmark |
| `selectable_countries` | `list[dict]` of `{tag, history_en, history_zh, minor, label:[...]}` — the playable nations + their hover blurb. `minor: true` = small-flag row; omit for a featured (big-portrait) nation |
| `filters` | 1.19 bookmark filter tokens (`new_content` / `continent`) → export emits `filters = { … }` |
| `name_en` / `name_zh` / `desc_*` | bookmark title/subtitle loc |

No raw-script fields.

### Common quirks
- **A bookmark card panel shows a limited number of focus-icon slots** — don't overfill `label`.
- Featured nations write no `minor` line; small-flag nations write `minor: true`. There is no `major`
  key (writing `major` errors in-game).
- `default_country` auto-shows without needing its own entry; keep it in `selectable_countries` too if
  it should be individually listed.
