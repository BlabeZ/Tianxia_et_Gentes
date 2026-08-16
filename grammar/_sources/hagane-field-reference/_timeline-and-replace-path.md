# Timeline & replace_path — non-1936 starts, total conversions, and the two override mechanisms

You need this page when the story does not start in 1936 — an earlier era, an alternate future, a whole
new timeline (TC / 架空时间线) — and whenever you touch `replace_path`, the sharpest tool in the mod
descriptor and the one whose misuse produces the least-debuggable CTDs.

## Two override mechanisms — know which one you're holding

| | Same-name file shadowing | `replace_path` |
|---|---|---|
| Granularity | **one file** | **a whole directory** |
| What it overrides | the same path in vanilla **or any earlier-loading mod** (later loader wins) | **vanilla only** — other mods' files are untouched |
| What survives | every other file in that directory still loads | vanilla's entire directory is ignored; only the files YOUR mod ships there exist |
| Failure mode | filename off by one character → BOTH definitions load (double-define) | declared but files missing/partial → the category is empty → CTD |
| Use it for | overriding one vanilla/base file: a state file, one event file, one bookmark file | wiping a vanilla category you fully re-supply: `common/bookmarks`, `common/ideologies` |

Default to same-name shadowing. Reach for `replace_path` only when the design is "vanilla's version of
this whole category must not exist".

## replace_path — three details, each a real failure class

1. ⚠️ **An emptied directory = CTD.** `replace_path` removes vanilla's whole directory. Declare it and
   ship nothing (or a partial set) and the game boots with that category empty. The platform's own
   ideology export is the rule to copy: the complete file and the `replace_path` line are generated
   together, strictly consistent — if the full file cannot be produced, no `replace_path` is added
   either (see `ideologies.md`). Hold your raw files to the same standard: full replacement set, or no
   replace_path.
2. ⚠️ **The line must be in the OUTER `mod/<name>.mod`.** HOI4 reads the `.mod` file listed in
   `dlc_load.json` — NOT the inner `mod/<name>/descriptor.mod`. The platform export emits BOTH with the
   same content, so a fresh install is correct. But after a player hand-reinstalls or updates the mod,
   **re-verify the outer `.mod` still carries the replace_path lines** — a stale outer file silently
   resurrects the vanilla directory. Real case: vanilla's 1936 bookmarks reappeared, the player
   unknowingly started the wrong scenario, every vanilla dated block fired against a non-1936 world →
   access-violation CTD blamed on mod content for days. The fix was two descriptor lines.
3. **It only strips vanilla.** `replace_path` never touches another mod's files. To override a BASE
   MOD's file, use same-name shadowing — your mod loads later, so your file wins.

## Platform entry points (both shipped)
- **Per-file** — `POST /api/projects/{pid}/raw-files` `{dest_path, content, generate_replace_path}`.
  With `generate_replace_path: true` the file's **parent directory** is merged into the descriptor's
  replace_path list. Binary variant `POST /raw-files/binary` (multipart `dest_path` + `file`, ≤25 MiB).
  Most raw overrides should leave it `false` — same-name shadowing usually suffices.
- **Per-export** — `GET /api/projects/{pid}/export/download?replace_paths=common/bookmarks`
  (comma-separated directories).
- **MCP** — template-based raw files only: `create_raw_from_template` writes a starter file to a fixed
  whitelisted path (`defines` · `bop` · `music` · `peace_conference` — see `defines.md` ·
  `balance-of-power.md` · `music.md` · `peace-conference.md`; `list_raw_templates` shows all).
  ⚠️ Arbitrary-path raw writes stay **REST-only** by design — drive them with your PAT.

## Non-1936 start checklist — three dates, one value
1. **Bookmark** — `/bookmarks` `date` field (see `bookmarks.md`) = the scenario start date.
2. **Defines** — raw file `common/defines/<mod>_defines.lua`:
   ```
   NDefines.NGame.START_DATE = "1924.1.1.12"
   NDefines.NGame.END_DATE = "1954.1.1.1"
   ```
   Defines override per-key, additively — list only the keys you change; no replace_path needed.
3. **History** — your history / start-state content must describe the world AT that date.

All three must hold the **same date**, and add `replace_paths=common/bookmarks` (shipping your own
complete bookmark file) so vanilla's 1936/1939 scenarios cannot be picked. The mismatch symptom is
exactly the CTD in detail #2 above: the player starts a vanilla date your world was never built for.
The platform does not keep these three in sync for you — the checklist is yours.

## Dated blocks — why the FAR past is safer than the near past
Vanilla history is full of dated blocks (`1939.1.1 = { … }`); a dated block only executes when the
start date is **on or after** its date. Any pre-1936 start leaves all of them dormant — for free.

The difference is runtime: start in **1924** and twelve game-years later the campaign RUNS INTO
vanilla's scripted era (date-gated events and AI come due mid-game). Start in year **183** and that era
is ~1750 game-years away — it never arrives. 远过去比近过去安全.

The pain then moves somewhere honest: nothing fires wrongly, but the entire 1936 cast is still standing
on the map (anachronism — Germany, the USA, everyone). Recommended shape: a **regional TC** — fully
build only your stage (your countries, your region), and quiet the rest with the toolbox below, rather
than rebuilding the planet on day one.

## Suppression toolbox — what is already quiet, what you must silence
- **Dated blocks / date-gated triggers** — dormant at any earlier start. Free.
- **`is_triggered_only` events** — never self-fire; if nothing in your timeline calls them, silent. Free.
- **Residual MTTH / undated events** — same-name override the vanilla event FILE with a neutered copy
  (keep the namespace, empty the events or gate their triggers).
- **A vanilla country's focus tree** — put `load_focus_tree = <your_tree>` in its history; an explicit
  load beats tree scoring, so its 1936 tree never runs.

## 🚩 Red zone: changing a BASE MOD's start date (submod)
A base mod's world lives in the **event/focus layer** — world evolution does NOT auto-run. The world at
year X exists only as [start state] + [scripted beats the player plays through]; pick a different start
year and the engine will not simulate the gap to catch the world up. Changing a base mod's start date ≈
hand-writing every country's target-year start state = a mini-TC. The honest paths: **follow the base
mod's official bookmarks**, or knowingly accept the mini-TC workload.
