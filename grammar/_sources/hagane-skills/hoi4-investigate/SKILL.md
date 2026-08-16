---
name: hoi4-investigate
description: Use the moment a bug, regression, or "why is X broken" surfaces in your mod, BEFORE writing any fix: confirm the real mechanism against the live platform and your exported mod, verify the premise (don't trust memory, a prior report, or a green validate), and confirm root cause before you change anything. Invoke automatically on any bug report.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.

# HOI4 Investigate — root-cause before fix

The discipline to run on every bug: confirm the actual mechanism against the live platform and your
exported mod BEFORE touching anything. Premise drift, false-green signals, and guessed magnitudes are
the three ways a "fix" goes wrong here — each one sends real effort at a non-problem while the real
bug stays untouched.

## When to use
- Any bug report, regression, in-game crash, "it worked last time", "why is X broken".
- An agent/assistant reports "done" or "validate is green" on a fix.
- Before scoping any change off a plan doc, a backlog item, or a memory note.
- Auto-invoke on bug reports — do not start patching directly.

## Procedure / Principles

1. **Iron Law — root cause FIRST.** No fix, no edit, no PUT until you understand the actual mechanism.
   If you catch yourself proposing a change before you can point at the exact broken thing (the field,
   the entity, the exported line), stop and go find it.

2. **Verify the PREMISE before scoping.** Memory, plan docs, backlog items, prior audits, and status
   reports are all point-in-time and routinely stale — anything more than a few days old is suspect by
   default. Re-confirm the premise against the **current live state** before acting: GET the entity via
   the API, run the platform validate, or open your latest export and look. Red-flag phrases that
   REQUIRE re-verification: "the plan says…", "memory mentions…", "a previous pass found…",
   "should / probably / usually". A "this is still broken at that old state" assumption is often simply
   out of date — re-confirm the real current state, don't trust the note.

3. **A green signal short of in-game verification is NOT proof.** A `200` from a POST/PUT means the
   request was accepted, not that the content is correct. A passing platform validate checks a
   *curated* set of token-legality and cross-refs — it cannot know about tokens only the game resolves,
   so green validate ≠ works in-game. "I changed the field" is not proof either: re-GET the entity (or
   re-export) and confirm the change is actually present and targeting the right id. Verify against the
   **real artifact** — the freshly re-exported mod plus your own in-game `error.log` — not against the
   intermediate signal.
   - If an agent "fixed" it by inventing a mechanism you didn't expect, treat that surprise as a **red
     flag**, not as cleverness — go trace the real path yourself. A success report that satisfies the
     literal ask while sidestepping the real path is exactly how a bug survives a "fix".

4. **Measure before fixing magnitude-sensitive things.** Don't act on a guessed count ("we're dropping
   dozens of X"). Quantify against the real artifact first — GET the actual entities via the API and
   count them, or run the platform validate and read exactly what it flags — *before* you "fix" a drop
   that may turn out to be zero. A guessed magnitude has sent many a fix at a problem that wasn't there.

5. **Output discipline.** State the root cause with concrete evidence (the exact field / entity /
   exported line), THEN fix. If part of the cause is still unclear, fix what's proven and note the rest
   — never guess-patch just to turn a validate green.

6. **For an in-game CTD (crash-to-desktop), read the PLAYER'S OWN logs FIRST — before analyzing any mod
   content.** The game writes the ground truth to the player's own machine under
   `Documents\Paradox Interactive\Hearts of Iron IV\`. These are the player's own game-output files —
   always legitimate to read, and far faster than reasoning about content blind:
   - `logs\game.log` — the **last line** = the actual start date the game reached + the last subsystem
     loaded before the crash. This alone usually localizes the crash to a phase.
   - `crashes\hoi4_<timestamp>\exception.txt` — the real exception. `EXCEPTION_ACCESS_VIOLATION` means
     an engine null-dereference, which is exactly why nothing useful lands in `error.log` for that class
     of crash.
   - `crashes\hoi4_<timestamp>\dlc_load.json` (and the live one) — which mods/DLC were actually active,
     so you can rule out a mod/DLC conflict versus your own content.

   **Do NOT assume the start date from what your mod intends.** If the game loaded a *different* start
   than you designed — e.g. the player picked a vanilla start instead of your custom one — then dated
   history you assumed was dormant fires, and your whole analysis is off from the first minute.
   `game.log`'s last executed line is the ground truth: if it shows a start date you didn't intend, your
   custom start didn't take. Re-export from the platform, reinstall the fresh ZIP, and re-check
   `game.log` before touching anything else. (A multi-day crash hunt once ran entirely on the assumption
   of an early start; `game.log` showed the game was actually executing history years later — reading it
   first would have caught it in minutes.)

## Gotchas / anti-patterns
- 🚩 Patching off a memory note, backlog line, or prior report without re-confirming the current live state.
- 🚩 Accepting "validate is green" or "the agent says done" as evidence of a real fix.
- 🚩 Treating a surprising mechanism an agent invented as clever instead of as a red flag to re-check.
- 🚩 Trusting an estimated count instead of measuring it against the real artifact.
- 🚩 Verifying against an intermediate signal (a `200`, a green validate) instead of the re-exported mod + your own `error.log`.
- 🚩 Dismissing a reproducible in-game issue as "just a vanilla/environment problem" without reproducing it yourself in a clean setup.

## The fix path
Once root cause is confirmed, implement the fix **via the API** (see hoi4-build-api for route + field
shapes), then **re-export and re-verify**:
1. `POST /api/projects/{pid}/export/validate` — cross-refs closed, loc complete, assets shipped.
2. `GET /api/lint/tree-validation/{pid}` — token-legality + structure.
3. Fix everything they flag, `GET .../export/download`, load the fresh ZIP in your own HOI4, and read
   `logs/error.log` — the final gate for tokens the lint can't know about.

## Cross-links
- Fix via the API + route/field shapes + export idioms → **hoi4-build-api**.
- End-to-end mod orchestration (design → build → verify → fix loop) → **hoi4-mod-design**.
