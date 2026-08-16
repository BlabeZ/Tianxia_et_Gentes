# Super-event fields — `/super-events`

A super-event = a **fullscreen ceremonial moment** (big background + music + staged title/quote/button)
— the story-narrative weapon for dramatic beats.

| Field | Meaning |
|---|---|
| `number` | 4-digit id, unique per country per project |
| `country_tag` | owning country (empty = no country scope) |
| `picture_path` | fullscreen background image — **upload-only** (set via `{se_id}/upload-picture`; not a reference to an existing sprite) |
| `song_token` | music/song token played during the super-event |
| `auto_fire_on_startup` | bool — register an on_startup hook to auto-fire at game start |
| `auto_fire_after_days` | delay (days) before the startup fire |
| `options` | `list[dict]` of `{name_en, name_zh, effect, ai_chance}`; **empty = a single "Continue" button** |
| `title_en` / `title_zh` | headline line |
| `quote_en` / `quote_zh` | flavor quote line |
| `btn_en` / `btn_zh` | button label (empty falls back to an ugly literal — always set it) |
| `desc_en` / `desc_zh` | body text |

Raw-script: `options[].effect` = raw effect run when that button is clicked → `_raw-script-fields.md`.

### Common quirks
- **The picture is upload-only** — putting a vanilla sprite name in `picture_path` is ignored. Upload a
  background image, or the panel shows a gray placeholder.
- `number` is unique per country per project — a clash is a 409.
- To delay the fire, `auto_fire_after_days=N` alone is sufficient — it schedules at game start and
  fires N days in. `auto_fire_on_startup=true` is an OR'd enable switch (day-0 fire when `N=0`),
  not a prerequisite for the delay.
- MCP requires a reachable trigger: set auto_fire_on_startup=true or auto_fire_after_days>0; a dormant call is rejected.
