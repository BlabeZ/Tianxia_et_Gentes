---
name: hoi4-build-localisation
description: Use when working on any HOI4 mod TEXT on the platform — localisation/localization, translation, loc keys, multi-language text, English/Chinese text, colored text (§G…§!), dynamic/scripted loc, or the whole-mod AI translate feature. Loc is CROSS-CUTTING (every entity carries loc fields; you never hand-write loc files) — this card gives the derived-key model, the per-entity filling discipline, dynamic & colored text, and the translate API. Invoke whenever filling name/desc/title fields, adding languages, or bulk-translating a mod.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.


# HOI4 Build Card · Localisation

> **A "build card" = the thin bridge between the platform form, the HOI4 output, and the player
> experience.** Localisation is the one card that is NOT a workbench: there is no `/localisation`
> resource to POST to. Every entity (focus, event, idea, decision, character, country, …) carries its
> own loc fields, and the export derives all keys and emits all `localisation/<lang>/*.yml` files for
> you. This card carries the derived-key model, the per-entity filling discipline, dynamic/colored
> text, and the whole-mod AI translate — the things no single workbench card owns.
>
> Route table / transport / auth → **hoi4-build-api**. Per-entity field shapes →
> `field-reference/<workbench>.md`.

## 0. Two engine facts that rule everything (paid-for lessons — read first)

- 🔴 **Loc KEYS may only contain `[A-Za-z0-9_.'-]`.** One non-ASCII character in a KEY (an `ö`, a
  Chinese character, a space) silently kills **every line AFTER it in that loc file in-game** — no
  error, the rest of the file just stops existing. Accents and full Unicode are fine in **VALUES**,
  never in keys. Since every loc key derives from an entity id (see §1), the practical rule is:
  **keep every entity id pure ASCII.** Put the fancy text in `name_en` / `name_zh` etc.
- 🔴 **HOI4 does NOT fall back across languages at runtime.** The engine reads ONLY the active
  language's files; a language file missing a key shows the raw key string to the player
  (`my_focus_name` instead of a name). "English exists, so Chinese players will see English" is
  FALSE — they see the key. This is why the platform emits symmetrically (§1) and why you fill both
  languages (§2).

One more engine fact for hand-checkers: duplicate loc keys are not won by load order the way script
files are. A file that redefines a key another mod (or vanilla) already defines only wins if it sits
under `localisation/<lang>/replace/` — otherwise the redefinition loses **silently**. The platform's
export handles placement for you; the fact matters when you inspect an exported zip or debug "my
rename didn't show up".

## 1. The derived-key model — you fill text, the export writes the files

You never hand-write a loc file and you never type a loc key for standard entities. You fill
per-language TEXT fields on the entity; the export:

1. **derives the keys** from the entity id, per a fixed scheme:

| Entity | Text fields | Derived key(s) |
|---|---|---|
| Focus | `name_en`/`name_zh` · `desc_en`/`desc_zh` | `<focus_id>` · `<focus_id>_desc` |
| Focus / Decision | `effect_tooltip_locs` (dict `{lang: text}`) | `<id>_et_tt` (+ injected `custom_effect_tooltip`) |
| Event | `title_en`/`title_zh` · `desc_en`/`desc_zh` | `<event_id>.t` · `<event_id>.d` |
| Event option | `name` (the KEY, auto `<event_id>.<a|b|c…>` if blank) + `name_en`/`name_zh` (button text) | the option key itself; `effect_tooltip_en/zh` → `<opt_key>_tt` |
| Idea / spirit | `name_en`/`name_zh` · `desc_en`/`desc_zh` | idea id keys |
| Decision / category | `name_en`/`name_zh` · `desc_en`/`desc_zh` | decision/category id keys |
| Character | `name_en`/`name_zh` (display name) · `desc_en`/`desc_zh` (bio) | character id keys |
| Country | `name` or `name_en`/`name_zh`; `name_<ideology>` (+ `*_zh`) per-government names | tag-based keys |

2. **emits the language files** — `l_english` / `l_simp_chinese` (and any other locale in the
   project's export set, §4) under `localisation/<lang>/`, correctly encoded, correctly headed.

3. **emits symmetrically**: fill only one language and BOTH language files still get the key (the
   other side carries fallback text), so no player ever sees a raw key. But the export flags a
   **loc-symmetry warning** for every one-sided field — a clean mod fills both.

**As an AI agent, filling both languages yourself IS the normal path** — you can translate inline
while you build, at zero extra cost. The whole-mod translate feature (§4) is the convenience path
for bulk gaps and for adding whole extra locales, not an excuse to author one-language entities.

Some entities also accept full locale dicts (`display_name_locs` / `description_locs`,
`{lang: text}`) alongside the `*_en`/`*_zh` shorthand — GET one entity of the type (per
**hoi4-build-api** §1) to see which shape it carries before assuming.

## 2. Filling discipline per entity type

- **Every entity you create**: fill `*_en` AND `*_zh` at creation time. Retro-filling after a 200-
  entity build session is strictly worse than translating inline as you go.
- **Entity ids** (focus_id, event namespace, idea id, decision id, …): ASCII only, ever (§0). An id
  like `görlitz_pact` poisons the derived key and thus the loc file.
- **Event options**: `name` is the loc KEY, `name_en`/`name_zh` is the button text — don't put
  English prose in `name`. Never key an option `.t`/`.d` (collides with the auto title/desc keys —
  use `<id>.optd` for a 4th option). → **hoi4-build-events**.
- **Variable/flag rewards have NO auto-tooltip** — a focus/decision whose only reward is
  `set_variable`/`set_country_flag` shows an EMPTY effect box. Fill `effect_tooltip_locs`
  (focus/decision) or per-option `effect_tooltip_en/zh` (events); the export injects
  `custom_effect_tooltip` + the loc lines. This is also the designated home for colored reward text
  (§3).
- **Reusing a vanilla entity id** (e.g. re-stating a vanilla character): vanilla's own loc may win
  for that key at runtime (see the `replace/` fact, §0). If your text MUST show, prefer a
  mod-unique id.

## 3. Dynamic & colored text (inside VALUES)

All of these live in the loc **values** you type into the `*_en`/`*_zh` fields:

- **Color codes**: `§G` green · `§R` red · `§Y` yellow · `§B` blue (more exist), always closed with
  `§!`. Example: `§GGain 50 Political Power§!`. Unclosed codes bleed into the following text.
- **Variable interpolation**: square-bracket syntax `[?var_name]` renders the variable's current
  value — the standard way an effect tooltip shows a live number.
- **Scripted localisation**: `[GetX]` in a value dispatches to a `defined_text` block that resolves
  different text by trigger (e.g. a title that changes with ideology). Create these via the
  `/scripted-localisations` resource: `name` = the dispatch symbol you call as `[GetName]`, `body` =
  the raw `defined_text` block (it re-includes its own `name = X` line); duplicate `name` is a 409.
  Field details → `field-reference/scripted-localisations.md`.
- These tokens are ENGINE MARKUP, not words — any translation (yours or the AI's) must carry every
  `§…§!`, `[?…]`, `[Get…]`, `\n` through **verbatim**. The whole-mod translate enforces this with a
  validator (§4); when you translate inline, you are the validator.

## 4. Whole-mod AI translate (project-scoped, AI-powered)

Two routes under `/api/projects/{pid}/translate` (auth per **hoi4-build-api** §2):

- **`GET /api/projects/{pid}/translate/languages`** →
  `{"languages": [{"code": "zh", "name": "…"}, …]}` — the supported target catalog: every HOI4
  locale (`en`, `zh`, `ru`, `fr`, `de`, `es`, `ja`, `ko`, `pl`, `pt` — `pt` is Brazilian
  Portuguese, the only Portuguese HOI4 ships). English is listed too: the source language is
  **auto-detected**, so a Chinese-authored mod's most useful target IS `en`.

- **`POST /api/projects/{pid}/translate/run`** — body:

```json
{
  "target_langs": ["zh", "ru"],
  "persist": true,
  "source_lang": null,
  "overwrite": false,
  "model": null, "api_key": null, "base_url": null
}
```
  - `target_langs` (required): short codes from the catalog; an all-invalid list → 400. A target
    equal to the resolved source is skipped (reported in `skipped_same_as_source`).
  - `persist` (default **false**): false = dry run, returns the full report + translations without
    writing anything. True = writes translated values into the entities' own loc fields (the same
    fields §1 describes — there is no separate loc store) **and** auto-adds every locale that
    actually produced translations to the project's `export_languages` so it ships.
  - `source_lang` (default null = auto-detect from the mod's own text): only set it to override
    detection.
  - `overwrite` (default **false**): false = fill blanks only — existing non-blank human text is
    never replaced. Only set true when the author explicitly wants existing text regenerated.
  - `model` / `api_key` / `base_url`: optional BYOK overrides, same semantics as the AI panels.
    **A daily AI-translate quota applies** (429 with a JSON body when exhausted); runs that bring
    their own `api_key` are exempt.

  Response (both dry-run and persist):

```json
{
  "source_lang": "en", "source_lang_origin": "detected",
  "skipped_same_as_source": [], "total_keys": 412,
  "persistable_keys": 401, "unpersistable_keys": 11,
  "languages": { "zh": { "lang": "zh", "translations": {"<key>": "<text>"},
    "coverage": { "translated_count": 400, "total": 412, "pct": 97.1,
                  "missing_keys": ["…"],
                  "markup_violations": [{"key": "…", "missing_tokens": ["§!"]}] } } },
  "persisted": 400, "blocked": 1, "kept_existing": 0, "skipped_empty": 0,
  "export_languages_added": ["zh"]
}
```
  - **The markup guard is enforced**: every translation is checked for verbatim survival of §-codes,
    `[…]` brackets and escape sequences; a violating string is **refused persistence** (counted in
    `blocked`, detailed in `markup_violations`) rather than allowed to break the game's text engine.
  - Read `coverage.pct` + `missing_keys` per language and re-run (or fill by hand) until clean.

**Which languages does the export actually emit?** The project meta field `export_languages`
(visible in `GET /api/projects/{pid}`) is the emit set — a locale you translated but never added
there ships nothing. A `persist=true` translate run maintains it for you
(`export_languages_added`); manual/inline translations into a new locale may require you to check it
yourself.

## 5. Self-check after building + common traps

GET your entities back and assert: every id ASCII; both `*_en` and `*_zh` filled on everything
player-facing; every §-code closed with `§!`; `effect_tooltip` filled wherever the only effects are
variables/flags. Then `POST /api/projects/{pid}/export/validate` — it reports **loc completeness in
both languages** plus cross-refs and assets. The in-game check (load the exported zip, switch the
game language, read the actual screens + `logs/error.log`) is the final gate: key-charset kills and
`replace/` losses are silent to every lint.

- 🔴 non-ASCII char in an entity id → derived loc KEY is illegal → every later line in that loc
  file silently dead in-game (§0).
- 🔴 filling only one language → players of the other language get fallback text; skipping BOTH →
  raw keys on screen. The engine never falls back across languages.
- 🔴 hand-writing loc files / hand-typing `.t`/`.d` keys → fights the derived-key export; fill the
  entity fields instead.
- 🔴 translate `persist` defaults to FALSE — a "successful" run that wrote nothing usually means
  you forgot it. And `overwrite=true` regenerates existing human text — off unless asked.
- Unclosed `§G` bleeds color into following text; a translation that drops `§!`/`[?var]` is blocked
  from persist — fix the value, don't fight the guard.
- Option key `.d`/`.t` collision → **hoi4-build-events** §5.
- A locale missing from `export_languages` ships nothing, however complete its translations.

## Cross-links
- Route table / transport / GET-then-POST protocol / validate endpoints → **hoi4-build-api**.
- Event title/desc/option keys + per-option effect tooltips → **hoi4-build-events**; focus
  name/desc + `effect_tooltip_locs` → **hoi4-build-focus**.
- Scripted localisation (`defined_text`, `[GetX]`) — cookbook → **hoi4-build-scripting**; field
  shapes → `field-reference/scripted-localisations.md`; cross-entity variable/flag wiring that those
  texts display → **hoi4-wiring**.
- "My text doesn't show in-game" / raw keys on screen / half a file missing → **hoi4-investigate**
  (verify the premise: language active, key derived, id ASCII, locale exported).
