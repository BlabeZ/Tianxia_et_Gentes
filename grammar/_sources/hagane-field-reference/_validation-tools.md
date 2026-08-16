# Validation tools — let the platform check correctness for you

Two **read-only** endpoints turn "did I wire this right?" into a query, instead of you grepping files.
They are not authoring surfaces — they're how you catch mistakes before the game does.

## Cross-reference graph — `/relations`
"Who references whom" across your project's entities (a focus that fires an event, a decision that adds an
idea, a character a focus unlocks…).
- `GET /api/projects/{pid}/relations/graph` — the full edge list.
- `GET /api/projects/{pid}/relations/entity/{kind}/{source_id}` — one entity's outgoing + incoming refs.
- `GET /api/projects/{pid}/relations/country/{tag}` — a country-scoped slice.

Each edge tells you whether the target **`resolved`** — a `resolved: false` edge is a dangling reference
(a typo'd event id, a focus that doesn't exist) that the export would silently drop. Check this before
export to find broken wiring.

## Scripted-symbol index — `/scripted-symbols`
Resolves every `scripted_effect` / `scripted_trigger` / `scripted_localisation` symbol: where it's defined
and every place your focus/event effect text calls it — and flags **used-but-undefined** symbols and
name collisions.
- `POST /api/projects/{pid}/scripted-symbols` (multipart: upload your `common/scripted_*/` source files)
  then `GET` the index. Use it to confirm a `scripted_effect` you call by name is actually defined, and
  that no two symbols collide on one name.

## The validation you'll use every build
Beyond these two, the two endpoints every build should run before the in-game pass:
- `POST /api/projects/{pid}/export/validate` — cross-refs closed, loc complete in both languages, assets
  shipped.
- `GET /api/lint/tree-validation/{pid}` — token-legality + structural lint.

Run all of these on the platform; your own game's `logs/error.log` is the final gate for the rare token
none of them can know about.
