# Peace conference — `common/peace_conference/` (re-price actions · steer AI bids · regroup tooltips)

The 1.12+ peace conference is **tuned, not scripted**: the four action types are engine-fixed —
`take_states` · `puppet` · `force_government` · `liberate` — and what you mod is what they COST
(`cost_modifiers/`), how much the AI WANTS them (`ai_peace/`), and how cost rows group in tooltips
(`categories/`). The big global levers (base costs, turn factors, contested-bid scaling) are defines
(`NDiplomacy.PEACE_*`) — see `defines.md`.

## Directory & naming rules
| Subdir | Root block | Purpose |
|---|---|---|
| `common/peace_conference/cost_modifiers/` | `peace_action_modifiers = { … }` | multiply action costs per condition |
| `common/peace_conference/ai_peace/` | `peace_ai_desires = { … }` | add / subtract AI desire per condition |
| `common/peace_conference/categories/` | `peace_action_categories = { … }` | UX grouping of cost rows |

Net-new filenames (vanilla uses `00_generic_peace.txt`, `<TAG>_peace.txt`, `00_peace_action_categories.txt`
— shadow one only to replace it). The platform's `peace_conference` template writes a cost-modifier
skeleton at `common/peace_conference/cost_modifiers/{key}_peace_cost_modifiers.txt`.

## The scope chain (memorise this)
| Scope | Is |
|---|---|
| `ROOT` | negotiator — whose turn it is |
| `FROM` | taker — owner AFTER the conference |
| `FROM.FROM` | giver — owner BEFORE the conference |
| `FROM.FROM.FROM` | the state (only when the action targets a state) |

From inside a nested scope, re-anchor via ROOT: `ROOT.FROM`, `ROOT.FROM.FROM.FROM`, ….

## Cost modifier entry (`cost_modifiers/`)
| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| *(block name)* | token | yes | — | net-new modifier id |
| `category` | category key | no | `other` | tooltip grouping — same-category rows display as one summed number |
| `peace_action_type` | one of the four, or an array `{ puppet liberate }` | yes | — | which actions it prices |
| `enable` | trigger block | yes | — | when the modifier is active — use `pc_*` triggers for mid-conference facts |
| `cost_multiplier` | decimal > 0 | yes | — | all active modifiers **multiply together**; keep ≈ 0.4–3.0 |

## AI desire entry (`ai_peace/`)
| Field | Type | Required | Meaning |
|---|---|---|---|
| *(block name)* | token | yes | net-new desire id |
| `peace_action_type` | one or array | yes | which actions it steers |
| `enable` | trigger block | yes | when it applies (same scope chain, `pc_*` triggers) |
| `ai_desire` | integer (%) | yes | **summed** across active desires; a total ≤ 0 means the AI won't take the action |

## Category entry (`categories/`)
```
peace_action_categories = {
    mymod_treaty = {
        name = MYMOD_PEACE_CATEGORY_TREATY   # loc key shown in tooltips
        # no "default = yes" — exactly ONE category game-wide may be default (vanilla's "other" is)
    }
}
```

## Minimal working example
The platform template drops this shape at `common/peace_conference/cost_modifiers/{key}_peace_cost_modifiers.txt`:
```
peace_action_modifiers = {

    # democracies liberate at half cost
    mymod_democratic_liberation = {
        category = ideology
        peace_action_type = liberate

        enable = {
            ROOT = { has_government = democratic }
        }

        cost_multiplier = 0.5
    }

    # taking a state the negotiator already controls is cheaper
    mymod_occupier_discount = {
        category = occupation
        peace_action_type = take_states

        enable = {
            FROM.FROM.FROM = { is_controlled_by = ROOT }
        }

        cost_multiplier = 0.8
    }
}
```
An AI-desire file follows the same pattern with `peace_ai_desires = { … }` and `ai_desire = 50`
instead of `cost_multiplier`.

## Platform entry points
- **Template** — MCP `create_raw_from_template(template="peace_conference", key="my_treaty")` / REST
  `POST /api/projects/{pid}/raw-files/from-template/peace-conference` `{key}` → the file above
  (key: lowercase `a-z0-9_`, 2–40 chars).
- **Any other path** (an `ai_peace/` or `categories/` file) — REST:
  `POST /api/projects/{pid}/raw-files` `{dest_path, content}`.

### Common quirks
- ⚠️ **Mid-conference the world is stale.** Ownership, control and diplomatic facts do NOT update
  between conference turns — plain triggers read the pre-conference world. For anything decided
  *during* the conference use the `pc_*` trigger family (`pc_is_puppeted`, `pc_is_puppeted_by`, …).
- **Multiplication collapses fast.** Cost modifiers multiply: three innocent 0.5s = 87.5% off.
  Vanilla's own guidance: stay within ≈ 0.4–3.0 per modifier, and `cost_multiplier` must be > 0.
- **`ai_desire` ≤ 0 is an off-switch.** Desires sum, and a non-positive total means the AI never bids
  that action — deliberately useful (e.g. stop ideology-mismatched AIs from puppet-spamming), and
  accidentally deadly (a broad negative desire silently lobotomises AI conferences).
- **Categories are pure UX.** They change tooltip grouping only — no cost effect; an unknown
  `category` lands the row under "other".
