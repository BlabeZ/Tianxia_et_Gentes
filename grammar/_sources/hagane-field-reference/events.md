# Event fields — `/events` + nested `/events/namespaces`

## Namespace (`POST /api/projects/{pid}/events/namespaces`)
| Field | Meaning |
|---|---|
| `namespace` | the event-id prefix (e.g. `sea` → events `sea.1`, `sea.2`) |
| `country_tag` | owning country |
| `scope_kind` | `own` normally |

## Event (`POST /api/projects/{pid}/events`)
| Field | Type / meaning |
|---|---|
| `namespace_id` | FK to the namespace |
| `event_id` | full id (`sea.2`) |
| `event_number` | the number after the dot |
| `event_type` | `country_event` / `news_event` / `state_event` |
| `title` / `description` | plain string, OR a `list[{text, trigger}]` for conditional text. (Or use the `*_en`/`*_zh` loc fields below and leave these blank) |
| `picture` | `GFX_event_*` sprite (or upload via `events/{id}/upload-picture`) |
| `is_triggered_only` | `true` = fires only when another effect calls it; mutually exclusive with `mean_time_to_happen` |
| `fire_only_once` | fire at most once per game |
| `hidden` | `true` = no popup (a silent helper/heartbeat event) |
| `major` | major-event styling |
| `trigger` | **raw trigger** — gate for a non-triggered event |
| `mean_time_to_happen` | **raw** MTTH body (`days = N modifier = { … }`); only when NOT `is_triggered_only` |
| `immediate` | **raw effect** — runs the instant the event fires (before the player sees it) |
| `after` | **raw effect** — runs after an option is chosen |
| `options` | `list[dict]` — see below |
| `timeout_days` | auto-pick the first option after N days |
| `auto_fire_on_startup` | `true` = fire on game start (init a variable system, etc.) |
| `auto_fire_after_days` | delay for the startup fire |
| `on_action_attach` | attach to an on_action hook (`on_startup`, `on_monthly`, …) instead of manual firing |
| `title_en` / `title_zh` | loc → export emits `title = <event_id>.t` |
| `desc_en` / `desc_zh` | loc → export emits `desc = <event_id>.d` |

## Option (each dict in `options`)
| Key | Meaning |
|---|---|
| `name` | the loc KEY (convention `<event_id>.<a|b|c>`; auto-generated if blank). ⚠️ don't use `.d`/`.t` — collides with title/desc keys |
| `name_en` / `name_zh` | the button text |
| `effects` | **raw effect** — what the option does |
| `hidden_effects` | **raw effect** — effects with no tooltip line |
| `trigger` | **raw trigger** — when this option is available |
| `ai_chance` | dict `{"base": N, ...}` — AI pick weight |

Raw-script fields → `_raw-script-fields.md`; tokens → `tokens.md`.

### Common quirks
- **Player-facing event** = `hidden=false`; **hidden helper** = `hidden=true` + `is_triggered_only=true`.
- Init an on-startup system with `auto_fire_on_startup=true`; a self-requeuing heartbeat re-fires itself
  with `country_event = { id = X days = N }` inside its own `immediate`.
- `scope_kind` does NOT gate in-game visibility — it only organizes the export file.
