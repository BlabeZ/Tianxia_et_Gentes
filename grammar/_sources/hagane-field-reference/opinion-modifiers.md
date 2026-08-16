# Opinion-modifier fields — `/opinion-modifiers`

Author reusable **opinion modifier** definitions (`common/opinion_modifiers/*.txt`) — these modify
diplomatic/trade relations between countries. A definition does nothing by itself; something must apply
it with `add_opinion_modifier = { target=<TAG> modifier=<modifier_id> }` from an event/focus/decision
effect (`guides/modifiers.md` §Opinion Modifiers).

| Field | Meaning |
|---|---|
| `modifier_id` | unique per project **+ country** — the block key under `opinion_modifiers = { ... }` |
| `country_tag` | which country's opinion-modifier file this belongs to. Blank on create defaults to the project's own tag (uppercased); if you send your own, send it already uppercase |
| `value` | the opinion-point delta the modifier applies |
| `decay` | monthly decay rate toward 0 (omit for a constant, non-decaying modifier) |
| `days` / `months` / `years` | duration before the modifier expires (omit for permanent) |
| `min_trust` / `max_trust` | value bounds on the trust the modifier can push |
| `trade` | bool — `true` = a trade-opinion modifier, `false`/omitted = diplomatic opinion |

### Common quirks
- `modifier_id` collision (same project + id) → `409`.
- **PUT is a real field-by-field partial update** — send only the keys you want to change; sending a
  field as `null` **deletes that key** (e.g. clear a `decay` you set earlier by sending
  `"decay": null`). An omitted key is left exactly as it was.
- Any extra key an imported definition already had survives your updates — only the fields in this
  table are ever touched; nothing else in the stored body is overwritten.
- Defining the modifier is not enough to see it in-game — wire the apply side
  (`add_opinion_modifier`) from wherever you want the relation change to trigger.

Raw-script effect that applies this → `_raw-script-fields.md`; token vocabulary → `tokens.md`.
