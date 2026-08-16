# Editing an existing mod — import it, modify it, save it back

The journey for "I have a finished mod and want to change or continue it" (修补 / 续作). It is a
distinct project identity with its own export semantics — not a submod.

## Loaded-existing vs submod — two different projects

| | Loaded-existing mod | Submod |
|---|---|---|
| Project shape | `dependencies: []` + `is_loaded_existing_mod: true` (set at creation by the load-existing import flow) | `dependencies: ["<base mod>"]` |
| What the project holds | the WHOLE mod's entities (`source: "imported"`) + your changes | ONLY your content — the base mod loads at runtime |
| Main export operation | **save back into the original mod** (append / diff channels below) | standalone additive zip that loads AFTER the base — **never append** |

Extending a mod you don't own, that players keep running alongside your addon → that is a submod
(`skills/hoi4-submod`). This page is for when the original mod itself is the thing being edited.

## The flow
1. **Import the whole package** via the platform's import flow (upload → scan-and-parse). Entities land
   with `source: "imported"`.
2. **Edit** through the normal workbenches. Touching an imported entity flips its `source` to
   `created` — it now counts as yours. New entities are `created` from birth.
3. **Export** — pick the artifact by intent:

| You want | Call | Semantics |
|---|---|---|
| a patch/addon (your changes + additions only) | `GET /export/download` (default) | emits `source="created"` only — everything you touched or added |
| the full mod re-emitted | `GET /export/download?include_imported=true` | everything, incl. untouched imported entities |
| the original mod UPDATED in place | `POST /export/append-to-existing` — multipart `base_mod_file` (the original mod zip) + `include_imported` + `replace_paths` | merges your platform output over the original zip, platform-wins on path conflicts; the `X-Merge-Conflict-Count` response header reports the overlap |
| conflict-by-conflict control | `POST /export/diff-preview` (dry-run conflict report), then `POST /export/diff-resolve` (same inputs + your per-path choices) | per-entity conflict reports for the diffable entity types; everything else falls back to the append merge |

`GET /api/projects/{pid}/full-mod-files` returns the same emit as a JSON file tree (text `content` /
binary `content_b64`) — for writing straight into a local mod folder instead of downloading a zip.

## Notes that save a day
- ⚠️ **Don't re-package base content into an addon.** If the artifact loads after the original mod, the
  default created-only export is the right one; `include_imported=true` would duplicate the entire
  original inside your patch — a huge zip and double definitions.
- **Changing what vanilla already ships** (a vanilla character, event file, state) → prefer a same-name
  file override over replace_path — the two mechanisms are contrasted in
  `_timeline-and-replace-path.md`.
- 🚩 **25 MiB binary cap.** The raw-files binary channel (`POST /raw-files/binary`) hard-caps at 25 MiB
  per file and is a per-file override hatch, NOT a bulk asset pipe — the import flow already carries
  the mod's own assets, so don't re-funnel a big mod's binaries through raw one by one. A single
  binary over 25 MiB (a whole-map `.bmp`, a long `.ogg`) has no platform channel at all.
