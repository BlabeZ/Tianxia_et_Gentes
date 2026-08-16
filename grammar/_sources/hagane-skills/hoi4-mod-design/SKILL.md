---
name: hoi4-mod-design
description: Use at the START of a new HOI4 mod / major content project AND to drive it end-to-end. Turns a creative brief / concept docs / a "story idea" into a PLAYABLE mod — design (base-mod audit, feasibility-root, decision-locked bible, author-facing design doc, phased roadmap) THEN the build→export→game-verify→fix loop — structured so the author only does (1) conversation and (2) in-game verification; the agent does all design + all building via the authenticated API. Orchestrates hoi4-submod (build), hoi4-investigate (root-cause), then in-game verification by the author (ship). Invoke when starting or running a mod project.
---

> **Keep this library fresh (auto-update)**: at the START of a session, before relying on any
> recipe here, run `git pull --ff-only` once from this repository's root. Skip silently if you
> are offline or this is not a git checkout — never let the update block the actual task.
> These recipes track the live hagane.works platform; a stale copy may describe old field shapes.

# HOI4 Mod Design — concept docs → playable mod (design + build-verify loop)

The methodology that turns a pile of lore/idea docs into a **decision-locked design bible**, then drives
**build → game-verify → fix** until it's playable — so the author only talks and tests in-game, and
building never goes "one step, hit a base-mod fact, re-decide". Proven on both a submod-on-a-big-base-mod
build and a from-scratch standalone with custom mechanics.

## When to use
- You have a creative brief / concept docs / a story idea and need to turn it into a playable mod.
- Starting OR running a new mod / major overhaul — especially a submod on a big base mod (TNO / KR / TFR).
- This is the **end-to-end orchestrator**; it delegates build mechanics to **hoi4-submod** / **hoi4-build-api**.

## The one principle
**Front-load the audit + design bible; never go step-by-step.** Per-phase rediscovery of base-mod facts
breeds inconsistency and rework. A decision-locked bible up front turns building into mechanical fill-in.

## Operating model — the author does conversation + game verification, nothing else
The whole chain is built so the **author's only two jobs** are: (1) give creative direction / answer design
questions in **chat**, and (2) load each export **in-game** and report what they see. **The agent does
everything else** — all design, all building via the authenticated API, all export + self-verify.
- **Author never touches the workbenches; the agent never asks them to click the UI.** If you're about to
  say "go open the focus workbench and…", stop — you do it via the API.
- **Two feedback channels only**: **chat** (decisions, bugs described in words) and **the game** (does it
  load + play right). Parts 1-2 below are built around exactly those two.
- **Design-conversation cadence (what makes this click for authors).** Inside the chat channel: the agent
  carries ALL the heavy lifting — research (historical/factual), platform recon, numbers/balance,
  building — and the **author only gives creative direction + makes taste/design judgments**. Always
  **recommend-then-let-the-author-decide**: lead every fork with your pick + reasoning, never dump open
  questions. Work in **coherent chunks, then pause for the author to review the logic** before moving on —
  don't run the whole design end-to-end without check-ins.

## Part 1 — Design (produce the decision-locked plan)

1. **Capture the vision from the AUTHOR'S source only.** Creative direction = the author's brief / lore /
   timelines / chat. For an overhaul, the base mod is **mechanical baseline, never creative authority** —
   don't let its canon pollute the author's story. Read every source doc; inventory every lore element,
   named entity, timeline beat, puppet, mechanic (this inventory is what you gap-check at step 5).
   - **If the author's input is thin/unstructured**, hand them **`CONCEPT_TEMPLATE.md`** (companion): hook ·
     world · base mod & reuse-vs-original · nations · timeline · start dates · **faction/alliance
     structure** · puppets · set-pieces · leaders · map · open-TBDs. Blanks become your first question
     list — "TBD" is fine.

2. **Audit the base mod (overhauls/submods only).** Fan out parallel **read-only** analysis — one pass per
   playable nation + one cross-cutting. Per nation, the **5-point map**: (1) start state (ideology
   group+subtype, leader token, situation, ideas, faction/puppets) · (2) storyline (focus-tree ids + size +
   themes, event chains, character tokens) · (3) custom mechanics · (4) **dissonance surface** (what base
   content *contradicts the new vision*, severity — the real risk) · (5) **build-on** (reframe
   rename/redirect vs gut). Cross-cutting: ideology-system map (base mods redefine it), puppet structure,
   **global dissonance sweep**. **Audit what the bookmark ACTUALLY loads, not the raw entity counts** — big
   base mods ship dead-code / cut / debug-gated arcs alongside the live one, so raw focus counts mislead;
   separate live from dead by what the active bookmark and start-state actually load (`load_focus_tree`
   wiring, game-rule gates, debug-only flags). And **re-verify a prior audit's conclusions before locking
   on them** — an earlier pass (even your own bible's) can mis-tag a dead-code arc as live, throwing off
   size / dissonance / reuse verdicts.
   - **Query the base-mod reference index instead of reconstructing every fact by hand (submods).** Once the
     declared base mod is ingested into the platform (submod reference layer — see **hoi4-submod**), the
     audit can query the **base-mod reference index** for real entities instead of reconstructing every
     token by hand, and the platform's **cross-ref lint flags undefined base-mod
     `country_tag`/`ideology`/`state`/`focus`/`decision` references live**, while the **reference pickers
     autocomplete** from those base-mod entities. This COMPLEMENTS, not replaces, the dissonance/build-on
     analysis. **Caveat: this only kicks in AFTER the base mod is ingested** — until then cross-ref keeps
     its trust-all fallback and gives no base-mod flags.

3. **Find the feasibility root.** Dissonance can *look* world-level but be **single-rooted** — trace,
   through the base-mod reference index / cross-ref, where the key global flags get **set**. If the cascade
   hangs off one suppressible event (e.g. a leader's death → succession), cutting that root leaves the
   reactive content **dormant** (its triggers never fire) — feasible without rewriting the world.
   Multi-rooted = scope balloon. **Verify by tracing the actual setters, never assume.** This sizes the
   override job and flags what to redesign around.

4. **Write the design bible** (authoritative content doc). Sections: world overview · base-mod baseline
   (audit condensed) · **per-nation decisions** (vision → start state → story direction →
   keep/override/ignore → dissonance resolution → build depth) · **narrative timeline** (the story) · open
   creative forks · **build mapping** (each item → platform mechanism → roadmap phase). **Decide everything
   derivable; surface only genuine creative forks.** Tag provenance: `locked` / `mine-derived` /
   `open-for-author` — NEVER mislabel your derivation as the author's decision.
   - **Per-nation alt-history pattern (the reusable engine for historical mods) — history-spine → real
     dilemmas → axes → endings.** Don't invent branches per faction: (1) lay a **date-gated historical
     spine** of what actually happened (real events become focus nodes); (2) put the **divergence at the
     point history genuinely could have gone otherwise** (verify the real turning point, don't pick
     arbitrarily); (3) derive endings from that faction's **2 real structural dilemmas** (its actual
     historical weaknesses) as **2 orthogonal axes → 4 endings** — each ending the logical result of
     solving/not-solving each dilemma, never mood-flavor options. Reuse the SAME pattern across all
     factions → tonal unity + each faction's dilemmas come out distinct. (Worked e.g.: a warlord — spine of
     the real early-reign events; dilemmas = foreign-dependence × hollow-mandate; 4 endings = the 2×2; the
     historical bad-end becomes a *deterministic* failure-state, not a dice roll.)
   - **Lock TONE as a first-class decision early** (e.g. "strict-historical start + serious/logical +
     restrained prose") and write every string to it. Treat author tone feedback ("colder", "too gamey") as
     a **rewrite-pass trigger across all affected text**, not a one-line tweak.
   - **Tag historicity on every ending/branch** (historical mods):
     【history】/【near-history】/【counterfactual】/【heavy-counterfactual】. The mod premise itself is
     usually counterfactual — say so plainly. Counterfactual lines get **restrained prose that doesn't
     masquerade as fact**.

5. **Gap-audit the bible vs the source.** Cross-check the step-1 inventory against the bible. Catch
   omissions (cosmetic names, full puppet lists, secondary mechanics) and **decision-holes** (e.g.
   faction/alliance structure). Patch them in.

5b. **Domain-expert self-critique passes (before locking).** Review your own design wearing the expert hat
   the **non-expert author can't** — and report honestly, including where YOUR design is wrong (don't
   self-validate). For a historical mod: a **historian pass** (is the history right? which endings are
   counterfactual? is the premise honest?). For any scored/economy/meter mechanic: a **game-numbers pass**
   (does it scale across a full multi-year campaign? sanity-check against vanilla number ranges). Offer
   deep-research to nail specific facts the author flags.

6. **Write the author-facing design doc** (use **`DESIGN_DOC_TEMPLATE.md`**, companion). Strip **all**
   internal mechanism — no build phases, no audit internals, no platform detail. Keep: premise, world,
   timeline (gaps marked), nations, light build-order. **Questions at the bottom, tiered**: (A) story gaps
   only the author can write · (B) design calls (with your recommendation) · (C) quick confirms (each a
   `default`). Don't re-ask settled things. Write in the author's language.

7. **Lock a phased roadmap.** Sequence the work; mark **dependency boundaries** (additive-now vs gated on a
   platform capability) + depth allocation (which nations deep vs thin). This is the build order for Part 2.

## Part 2 — Build & verify (per roadmap phase · conversation + game only)

8. **Build the phase via the authenticated API** (→ **hoi4-submod** / **hoi4-build-api**). Create every
   entity the bible specifies for this phase: country / cosmetic name, focus tree, events, super-events,
   ideas/spirits, characters/leaders, bookmarks, history / start-state, decisions, tech (reuse base mod),
   states / puppets, en/zh loc. ALL via the authenticated API — never the UI, never ask the author to
   click. Platform limit to know: **states are form-level** (no province/border editing).

9. **Export + self-verify** (→ **hoi4-build-api** §5). Run the platform's **validate** + **tree-validation**
   before handing anything to the author: cross-refs closed, your effect lines actually emitted, assets
   shipped, loc complete in BOTH languages. **Fix everything the platform validation catches BEFORE handing
   the author an export** — don't burn the author's game-test on what validate would have found.

10. **Author game-verifies.** Hand the export with a SHORT, specific checklist ("load the 1962 start, pick
    GER, confirm leader = X, fast-forward past the succession date → no civil war, focus icons present").
    The author installs + reports **in words**. This is the only in-game step. (Align versions first —
    base-mod version mismatch = CTD that isn't your content.)

11. **Iterate on the report.** In-game issue → **hoi4-investigate** (root-cause against the REAL exported
    pipeline; don't guess, don't trust "export succeeded") → fix via API → re-export → re-verify. Loop
    until the phase is **accepted**, then next roadmap phase. Version exports (v1/v2…); keep the last
    accepted as the demo snapshot. Ship: hand the exported zip to the author to load in-game.

## Outputs (one project produces this set)
`_INDEX.md` (doc map) · `*_BASELINE_AUDIT.md` (submods) · `STORY_BIBLE_*.md` · `ROADMAP_LOCKED_*.md` ·
`DESIGN_DOC_*.md` · versioned exports (`export_test/*_vN.zip`). For content-heavy / custom-mechanic mods
also: `NATIONS_backbone*.md` (per-faction structures), `SPEC_<nation>_phaseN.md` (build-ready node-level
spec), `SYSTEM_<mechanic>.md` (global-mechanic full rules), `WORLD_<year>_setup.md` (start-state with real
state IDs), and a capability-recon note (for a custom mechanic — what the platform can build vs. what to
redesign).

## Gotchas / anti-patterns
- 🚩 Asking the author to click the workbench UI. They do chat + game only; the agent drives the API.
- 🚩 Spending the author's in-game test on what the platform would catch — run validate + tree-validation
  (step 9) first. **BUT export self-verify GREEN ≠ loads in-game**, especially for a standalone: the killers
  (bad effect/modifier tokens, `recruit_character` location, an undefined ideology, a capital-orphan
  country) are invisible to validate/cross-ref; expect a few export → `error.log` → fix iterations
  (v1→v2→v3 is normal). The in-game `error.log` pass is mandatory, not optional. (Mechanics + standalone
  start-state rules → **hoi4-submod**.)
- 🚩 Guessing a fix from an in-game report. Root-cause with **hoi4-investigate** against the real export.
- 🚩 Letting the base mod's canon drive the story. It's mechanical baseline only.
- 🚩 Going step-by-step (build → hit a base-mod fact → re-decide). The bible exists to prevent this.
- 🚩 Calling the dissonance unfixable because it's "everywhere." Check single-rooted first (trace the flag
  setters through the base-mod reference index).
- 🚩 Mislabeling design derivations as the author's decisions. Tag provenance; surface real forks separately.
- 🚩 Platform mechanism in the author-facing doc. The author cares about story + decisions, not how you build.
- 🚩 Rebuilding what the base mod already has. Most "dissonant" nations are reframe, not rebuild — audit
  build-on first.
- 🚩 Re-asking settled questions. Track what the author already decided.
- 🚩 Multi-nation overhaul writing shared state from the wrong line. Own faction creation in the LEADER
  nation's build (members only `add_to_faction`); agree cross-line global-flag names up front (each line
  inventing its own = silent breakage); never write one nation's history/events from a different nation's
  build.
- 🚩 Standalone (non-submod) mod: skip steps 2-3; bible / gap-check / author-doc / roadmap / build-verify
  still apply (build-on becomes "what vanilla + DLC give you"). Run a **capability recon** in their place
  (next bullet).
- 🚩 **Promising a custom mechanic before a focused platform-capability check.** Before you commit a bespoke
  mechanic to the author, confirm the platform can actually build it — which `on_action` hooks are available
  (`on_startup` / `on_monthly` / `on_capitulation` / …), which workbenches exist, whether standalone
  projects are supported. Check the **field-reference** + **hoi4-build-api** route table + **hoi4-wiring**;
  don't assume a feature exists because it'd be convenient, and don't assume it's missing either. If there's
  no buildable path, redesign the mechanic to what the platform supports — don't promise what you can't build.
- 🚩 **Scored/meter mechanic that accumulates unbounded over a multi-year campaign** — it overflows and can
  be idle-farmed, the bar loses meaning. Use **recompute-from-components each period** (sticky "earned" +
  current "positional"), clamped. And **don't expose the raw total/weights** to the player → show dimensions
  + qualitative tiers, else they min-max the number instead of role-playing.
- 🚩 **Hand-guessing vanilla data for a strict-history setup.** Don't invent state IDs, portrait/flag names,
  or start-state ownership — pull them from the platform's vanilla reference data / states picker. **Reuse a
  vanilla tag to white-pick its art** when a faction maps to one; note the state-granularity limit (you
  can't split a vanilla state's provinces — states are form-level).

## Companion (this skill's folder)
- **`CONCEPT_TEMPLATE.md`** — the author's fill-in INPUT brief (12-section concept checklist). Hand it at
  step 1; blanks become questions.
- **`DESIGN_DOC_TEMPLATE.md`** — the author-facing OUTPUT skeleton (step 6): premise · world · timeline
  (gaps) · nations · build-order · tiered questions A/B/C. Mechanism stripped.

## Depth — worked example (a submod on a big base mod)
A submod on a large base mod (TNO-style), reframing several base nations for a new "what if" without
rewriting the world. Vision from the author's user-story docs → **base-mod audit** (5-point map per nation
+ global dissonance sweep) → **feasibility root** (the whole dissonant cascade turned out single-rooted in
one leader-death → succession event; suppress that root and the reactive content stays dormant) → **design
bible** → **gap-check** → **author-facing design doc** → **locked roadmap** → **build (hoi4-submod) → export
+ self-verify → author game-tests → hoi4-investigate + fix → repeat per phase**. The payoff: a "world-level"
dissonance problem became a one-event override, so the submod shipped additive-on-canon.

## Depth — second worked example (a from-scratch standalone with a custom mechanic)
Standalone-on-vanilla (no base mod), strict-historical start, a custom accumulating "meter" as the soul
mechanic. **Skipped steps 2-3** (no base mod); ran a **capability recon** instead — confirmed the platform
supports standalone projects, a custom bookmark/ideology/tech, and the `on_monthly` / `on_capitulation`
hooks the mechanic needed, and confirmed it does NOT do map/province editing (so start-state stays at
state granularity).
- **Per-nation alt-history pattern applied to every faction** (history-spine + 2 real dilemmas → 2-axis 4
  endings), each with **historicity tags** — surfacing that only one faction had a true 【history】 ending,
  the rest counterfactual.
- A **historian critique pass** caught a premise-honesty point (the core premise was itself counterfactual);
  a **game-numbers pass** caught an accumulator that overflowed across a multi-year campaign → switched the
  meter to recompute-from-components + anti-score-chasing guardrails.
- Start-state resolved to **real vanilla state IDs** from the platform's reference data; reused vanilla tags
  to white-pick flags/portraits.
- Expect a few `export → error.log → fix` iterations before it loads clean — normal for a standalone.

## Cross-links
- Build workflow + additive-submod rules → **hoi4-submod**.
- API surface + payload shapes + export idioms → **hoi4-build-api**.
- Cross-entity wiring (focus fires event, on_actions, succession, scope-passing) → **hoi4-wiring**.
- Root-cause an in-game failure against the real export → **hoi4-investigate**.
