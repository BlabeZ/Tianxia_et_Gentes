# Special-project fields — `/special-projects`

Author DAG "special project" research nodes and their specialization tracks.
**DLC: Götterdämmerung** — only applies for players who own that DLC.

Two nested sub-resources: `specializations` (research tracks / facility types) and `projects` (the DAG
nodes). Plus `validate` (checks the DAG for missing parents / cycles).

> 🔴 **Not recommended right now — exports can fail to parse.** The free-text raw-script fields below
> (`resource_cost` / `project_output` / `complexity` / `prototype_time`) have a confirmed, reproducible
> export bug: some values produce a token HOI4's script lexer rejects (a token starting with a digit) or
> a project the engine can't resolve a category for. The exact trigger hasn't been root-caused yet.
> `/special-projects/validate` does **not** catch this — it only checks the DAG (missing parents /
> cycles), not script-lexing. Until this is fixed, treat this workbench as read/preview-only: building a
> special-project tree risks an export HOI4 refuses to load at all, not just a cosmetic gap.

## Project node (`POST /special-projects/projects`)
| Field | Meaning |
|---|---|
| `project_token` | unique string id of the DAG node |
| `specialization` | the specialization/track this node belongs to (**string token ref**, not an FK) |
| `country_tag` | owner (blank inherits the project's country) |
| `special_project_parent` | `list` of parent `project_token`s = the DAG prerequisite edges |
| `allowed` | **raw trigger** — who may access the project |
| `visible` | **raw trigger** — node visibility |
| `available` | **raw trigger** — availability gate |
| `resource_cost` | **raw script** resource-cost block |
| `project_output` | **raw script** output/reward block |
| `complexity` | **raw script** complexity value |
| `prototype_time` | **raw script** prototype-time value |
| `generic_prototype_rewards` | `list` of generic prototype-reward tokens |

Raw-script trigger fields → `_raw-script-fields.md`.

### Common quirks
- `specialization` and `special_project_parent` reference other nodes by **string token**, not int FK —
  the DAG edges are token strings.
- `complexity` / `prototype_time` / `resource_cost` / `project_output` are **free-text raw-script strings**,
  not typed numbers.
- Run `/special-projects/validate` to catch missing parents / cycles before export.
