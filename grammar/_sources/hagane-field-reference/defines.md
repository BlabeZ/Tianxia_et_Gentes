# Defines — engine constants (`common/defines/*.lua`)

Defines are the engine's exposed constants — **Lua assignments, not PDXscript** — controlling systems
that have no direct script hook: event/mission timings, research slots, diplomacy costs, combat math,
AI pacing. There is no defines workbench; you ship one small raw `.lua` file that overrides **only the
keys you change**. Vanilla's full key list lives in `/Hearts of Iron IV/common/defines/00_defines.lua`
(read it as a dictionary — never copy it, see below).

## Directory & naming rules
| Rule | Detail |
|---|---|
| Location | `common/defines/*.lua` — evaluated after the base game's defines, files in ASCII filename order, later files win per key |
| Granularity | **per key**: `NDefines.<Namespace>.<KEY> = value`, one assignment per line — no whole-file copies, no `replace_path` |
| ⚠️ **Never ship `00_defines.lua` / `00_graphics.lua`** | copying a vanilla defines file freezes EVERY constant at one patch's values; the next game update adds/renames keys your copy is missing → instability and crashes. Override per key in your own net-new file instead |
| ⚠️ **Never hand-write `START_DATE` / `END_DATE`** | when your project's start date ≠ 1936, the platform itself emits `common/defines/<mod>_defines.lua` carrying the timeline. Set the start date in **project settings**; a hand-written date define double-defines the timeline (the export lint flags the conflict) |
| Net-new filename | the platform template writes `common/defines/{key}_tweaks.lua` — clear of both reserved names above |

## Override idiom
```lua
NDefines.NGame.EVENT_TIMEOUT_DEFAULT = 30      -- default 13
NDefines.NCountry.BASE_RESEARCH_SLOTS = 3      -- default 2
```
- One assignment per line, **no commas or semicolons between lines** — a stray trailing comma is a
  crash on launch (each line is a separate Lua statement, not an array entry).
- Real but sandboxed Lua: `--` comments work; file access / `require` do not.

## Namespaces you'll actually touch
| Namespace | Governs | Example key (default) |
|---|---|---|
| `NGame` | core pacing: event/mission timeouts, game speeds | `EVENT_TIMEOUT_DEFAULT` (13) |
| `NCountry` | research slots, stability/war-support baselines, surrender limits | `BASE_RESEARCH_SLOTS` (2) |
| `NDiplomacy` | opinion/trust caps, truces, wargoal + peace-conference costs | `BASE_TRUCE_PERIOD` (180) |
| `NMilitary` | combat dice, XP caps, special-forces cap | `MAX_ARMY_EXPERIENCE` (500) |
| `NPolitics` | PP gain, leader recruit costs | `BASE_POLITICAL_POWER_INCREASE` (2) |
| `NProduction` | factory speed / efficiency ramp | `BASE_FACTORY_SPEED` (5) |
| `NTechnology` | research cost, ahead-of-time penalty | `BASE_TECH_COST` (110) |
| `NBuildings` | building level caps, capacities | `MAX_BUILDING_LEVELS` (15) |
| `NResistance` | resistance/compliance growth | `RESISTANCE_TARGET_BASE` (35.0) |
| `NAI` · `NFocus` · `NAir` · `NNavy` · `NSupply` · … | AI behaviour, focus, air/naval, supply constants | see vanilla `00_defines.lua` for the full list |

## Minimal working example
The platform's `defines` template drops this shape at `common/defines/{key}_tweaks.lua`:
```lua
-- engine-constant overrides: list ONLY the keys you change
-- (start date lives in project settings, NOT here)
NDefines.NGame.EVENT_TIMEOUT_DEFAULT = 30       -- events wait 30 days (not 13) before auto-resolving
NDefines.NCountry.BASE_RESEARCH_SLOTS = 3       -- every country starts with 3 research slots
NDefines.NDiplomacy.BASE_TRUCE_PERIOD = 365     -- truces last a year instead of 180 days
```

## Platform entry points
- **Template** — MCP `create_raw_from_template(template="defines", key="my_tweaks")` / REST
  `POST /api/projects/{pid}/raw-files/from-template/defines` `{key}` → the file above
  (key: lowercase `a-z0-9_`, 2–40 chars; `list_raw_templates` lists every template domain).
- **Any other path** — REST only: `POST /api/projects/{pid}/raw-files` `{dest_path, content}` —
  see `_timeline-and-replace-path.md`.

### Common quirks
- **A wrong key fails silently.** Lua happily assigns `EVENT_TIMEOUT_DEFAULLT = 30` — no error, no
  effect. Copy key names verbatim out of vanilla's `00_defines.lua`, then verify in game.
- **Defines are global and load-time.** They apply to every country and are read once at game start —
  restart to test a change; they cannot be flipped mid-game by script.
- **Balance keys cut both ways.** Peace-conference costs, tension scaling and AI pacing all live here
  and multiply through systems you don't see — change values in small steps, one at a time.

Non-1936 timelines (the full START_DATE story): `_timeline-and-replace-path.md`. Peace-conference
cost defines pair with `peace-conference.md`.
