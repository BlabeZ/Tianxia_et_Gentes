# Wargoal-type fields — `/wargoals`

Author custom **war-goal types** (`common/wargoal_types/*.txt`) — the casus-belli options a player picks
when justifying a war, each with its own cost, eligibility triggers, and peace-conference powers
(`on_generate_wargoal` / `on_justifying_wargoal_pulse` / `on_wargoal_expire` all key off these —
`guides/on_actions.md` §Wargoals).

| Field | Meaning |
|---|---|
| `wargoal_key` | unique per project. Must be **one HOI4 token** — no whitespace, `{`/`}`/`=`/`#`/`"` |
| `war_name` | the wargoal's display name — one token, or a quoted string if it needs spaces |
| `safe_scalars` | dict of **whitelisted** scalar keys only: `generate_base_cost` · `generate_per_state_cost` · `take_states_limit` · `take_states_cost` · `puppet_cost` · `force_government_cost` · `expire` · `threat` · `take_states_threat_factor`. Any other key → `422` naming the bad key(s). Each value = one token or one quoted string |
| `allowed` / `available` | **raw trigger blocks** — `allowed` gates who can ever pick this wargoal type; `available` gates when it's currently choosable |
| `take_states` / `puppet` / `liberate` | **raw trigger blocks** — eligibility for each peace-conference action this wargoal can grant |
| `advanced_raw_script` | escape hatch for any `key = value` entry **not** covered by the fields above (rare/edge tokens). 🔴 A key that IS one of the fields above (`war_name`, a `safe_scalars` key, or a block field) is **rejected** here with `"<key> belongs in the visual fields, not Advanced raw script"` — always use the typed field, never smuggle it through Advanced |
| `source_file` | import-preservation path (backslashes normalized to `/`) |

### Common quirks
- `wargoal_key` collision (same project) → `409`.
- `allowed` / `available` / `take_states` / `puppet` / `liberate` are validated as real HOI4 script on
  write — every entry must be `key = value`; a bare value or malformed block → `422`
  `"<field> contains malformed HOI4 script"`.
- `war_name` and each `safe_scalars` value go through a lighter **scalar** check (one token, or one
  quoted string if it contains whitespace) — not full script parsing, so a mistyped brace here reads
  as `"<field> must be one token or one quoted string"` rather than a script-parse error.
- **PATCH rejects explicit `null`** on every field in this table — `422`
  `"Wargoal update fields cannot be null"`. Omit a field to leave it unchanged; there's no "clear this
  field" via PATCH.
- `advanced_raw_script` on read is **derived**, not stored verbatim as one blob — the platform keeps
  your unknown entries in their original relative order and re-renders them; re-PUTting the same text
  back is safe (round-trips), but don't expect byte-identical whitespace of what you last sent.

Raw-script trigger fields → `_raw-script-fields.md`; token vocabulary → `tokens.md`.
