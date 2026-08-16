# Character fields — `/characters`

One character = one `role_type`. A person who is both a commander and an advisor = ONE character with
`has_advisor_role=true` (NOT two characters — that doubles them in-game).

| Field | Meaning |
|---|---|
| `name` | internal name/token base |
| `tag` | character token (auto-derived if blank; must be unique) |
| `country_tag` | owning country (blank = the project's country) |
| `role_type` | `country_leader` / `general` / `field_marshal` / `admiral` / `advisor` / `operative` / `scientist` / `theorist` |
| `has_advisor_role` | `true` → also emit an advisor block (dual role) |
| `replaces_vanilla_id` | overlay a vanilla character (advanced; usually false) |
| `skill` / `attack_skill` / `defense_skill` / `planning_skill` / `logistics_skill` / `maneuvering_skill` / `coordination_skill` | commander stats (maneuvering/coordination = admiral) |
| `military_visible` | **raw trigger** — when the commander is recruitable |
| `traits` | `list[str]` — commander traits (field: `common/unit_leader`) OR, for a **pure advisor**, put the advisor's trait HERE (preferred over `advisor_traits`) |
| `advisor_traits` | `list[str]` — traits for the advisor block of a dual-role char |
| `advisor_slot` | advisor category (`army_chief`, `high_command`, `political_advisor`, `theorist`, …) |
| `advisor_idea_token` | the advisor's idea id (auto if blank) |
| `advisor_cost` | PP to hire (default 150) |
| `advisor_available` / `advisor_visible` | **raw triggers** for the advisor |
| `advisor_removal_cost` | PP to fire (default -1 = not removable) |
| `advisor_modifier` | **raw flat modifier** for an explicit extra advisor effect |
| `advisor_on_add` / `advisor_on_remove` | **raw effects** when hired/fired |
| `ideology` | the leader's **sub-ideology** (for `role_type=country_leader`) |
| `gender` | `male` / `female` |
| `can_be_captured` | 1.19+ · `false` → emits `can_be_captured = no` (default `true` = vanilla, key omitted) |
| `always_show_on_actions_tooltip` | 1.19+ · advisor block · `true` → the advisor is always listed in on-actions tooltips (omit = vanilla default no) |
| `scientist_data` | dict for `role_type=scientist` |
| `operative_skill_level` / `operative_traits` / `operative_nationalities` / `operative_available` / `operative_bg` | for `role_type=operative` (LaR DLC) |
| `expire` | date the character expires (`1948.1.1`) |
| `name_en` / `name_zh` | display name loc |
| `desc_en` / `desc_zh` | bio loc |

Raw-script fields → `_raw-script-fields.md`; trait/slot tokens → validate on the platform.

### Common quirks
- **One active `country_leader` per ideology.** A second same-ideology leader is a dormant duplicate;
  do succession via an event (`kill_country_leader = yes` + `create_country_leader = { … }`).
- **Pure advisor's effect goes in `traits`** (the export coalesces `advisor_traits` → `traits` when
  `traits` is empty, but `traits` is the round-trip-safe field).
- Advisor slots and trait tokens are validated by the platform lint / your in-game `error.log` — POST and
  check rather than memorizing the full trait list.
- ideology emits a country_leader block only when role_type='country_leader'; role_type defaults to 'general'.
