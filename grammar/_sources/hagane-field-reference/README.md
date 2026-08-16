# Field Reference — which HOI4 token goes in which platform API field

This folder is the map from **HOI4's script vocabulary** onto the **platform's API fields**. It answers
"what do I put in the `completion_reward` field?" — not "what does a focus `.txt` file look like". You
build by POSTing fields; these files tell you what each field expects.

## How to use it
1. You're filling a workbench (focus / events / characters / ideas / decisions). Open the matching
   `<workbench>.md` here.
2. It lists each field, what it means, and — for fields that hold **raw HOI4 script** — which token
   vocabulary is legal (effects / triggers / modifiers). The shared vocabulary is in `tokens.md`; the
   list of which fields are raw-script (and how the export wraps them) is in `_raw-script-fields.md`.
3. POST the fields. The platform validates them for you (see below) and renders them in the web editor.

## The platform is the authority, not this file
`tokens.md` is a **filling aid** — the common, high-signal tokens with one-line meanings. It is
deliberately **not** an exhaustive dump of the HOI4 wiki (you don't need one to fill a field, and the
wiki is public if you ever do). The **source of truth for "is this token legal here"** is the platform:

- `POST /api/projects/{pid}/export/validate` — cross-refs, loc, assets.
- `GET /api/lint/tree-validation/{pid}` — token-legality + structure.

Write the token, POST it, let the platform tell you if it's wrong. Your own game's `logs/error.log` is
the final gate for the rare token neither the lint nor this file covers.

## Files
- `_raw-script-fields.md` — the master list of raw-script fields per workbench + the wrapping idiom.
- `_timeline-and-replace-path.md` — non-1936 starts / total conversions + the two override mechanisms
  (same-name file shadowing vs directory-level `replace_path`).
- `_editing-existing-mods.md` — the loaded-existing journey: import a finished mod, edit it, save it
  back (append / diff export).
- `tokens.md` — shared token vocabulary (effects / triggers / modifiers / scopes) as field-fillers.
- Per-workbench field maps:
  - **Story & politics:** `countries.md` · `ideologies.md` · `focus.md` · `events.md` · `decisions.md` ·
    `ideas.md` · `characters.md` · `custom-traits.md` · `bookmarks.md` · `history-files.md` ·
    `super-events.md` · `dynamic-modifiers.md` · `opinion-modifiers.md` · `modifier-definitions.md` ·
    `wargoals.md` · `scripted-snippets.md` · `scripted-localisations.md`
  - **Military & hardware:** `technologies.md` ⚠️ *not recommended right now* · `equipment.md` ·
    `sub-units.md` · `division-templates.md` · `division-deployments.md` · `oob-units.md` (air wings ·
    fleets · task forces · ships) · `states.md` · `mios.md` · `doctrines.md` · `special-projects.md`
    ⚠️ *not recommended right now* · `intelligence-agencies.md` · `autonomy-states.md`
    *(several are DLC-gated — each file flags which)*
  - **UI & validation:** `ui-panels.md` (界面机制 Builder — scripted_gui panels) · `_validation-tools.md`
    (the read-only cross-ref / scripted-symbol / lint endpoints that catch mistakes before the game does)
  - **Raw-file template domains** *(no dedicated workbench — start from a template: MCP
    `create_raw_from_template` / REST `from-template` routes)*:
    - `defines.md` — engine constants (`common/defines/*.lua`): per-key Lua overrides + the start-date red lines.
    - `balance-of-power.md` — two-sided struggle bars (`common/bop`): sides/ranges + the `set_power_balance` wiring.
    - `music.md` — radio stations (`music/`): `.asset` song defs + `.txt` station playlists + `.ogg` uploads.
    - `peace-conference.md` — conference tuning (`common/peace_conference/`): cost modifiers · AI desires · categories.
