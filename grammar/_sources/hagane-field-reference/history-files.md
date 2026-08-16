# History-file fields — `/history-files`

A history file = a country's **day-0 starting state**: politics, ideology support split, starting
ideas/focuses/tech, diplomacy, OOB pointers. One per country.

| Field | Meaning |
|---|---|
| `country_tag` | which country this file sets up (trimmed + uppercased) |
| `capital` | capital state id (**`0` = don't emit**, a sentinel — not a real state) |
| `set_politics_ruling_party` | starting ruling party / ideology group |
| `set_politics_election_frequency` / `_elections_allowed` / `_last_election` | election setup |
| `set_popularities_democratic` / `_communism` / `_fascism` / `_neutrality` | ideology support split (should sum to 100) |
| `set_research_slots` | starting research-slot count |
| `set_stability` | starting stability (**`-1.0` = don't emit**) |
| `set_war_support` | starting war support (**`-1.0` = don't emit**) |
| `add_ideas_extra` | `list` of national spirits/ideas active at start |
| `remove_ideas` | `list` of ideas to strip at start |
| `complete_national_focus_ids` | `list` of focuses pre-completed at start |
| `set_technology_ids` | `list` of techs pre-researched at start |
| `set_cosmetic_tag` | cosmetic rename tag |
| `set_oob` / `set_air_oob` / `set_naval_oob` | order-of-battle file pointers (the OOB stems from division-templates) |
| `set_autonomy` / `diplomatic_relation` | `list[dict]` structured diplomacy/subject setup |
| `startup_flags` | `list` of country flags set at day 0 |

No named raw-script effect/trigger fields — history is structured. (There is an advanced generic
`raw_script` escape-hatch that appends verbatim history script; prefer the structured fields above.)

### Common quirks
- `capital = 0`, `set_stability = -1.0`, `set_war_support = -1.0` are **sentinels meaning "don't emit"**,
  not real values.
- One history file per country — a duplicate `country_tag` is a 409.
- Don't set a country's capital to a state it doesn't own → in-game `capital … they don't own it`.
