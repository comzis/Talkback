# Triage labels

The skills speak in terms of five triage roles. This file maps those roles to the label strings used on `comzis/Talkback`.

| Role | Label in this repo | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Needs evaluating |
| `needs-info` | `needs-info` | Waiting for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified, and the unit loop checks every criterion. An agent can do it AFK |
| `ready-for-human` | `ready-for-human` | Needs a person: eval rows, accepting a live eval result, held-out, UI judgement, model choice, or host setup |
| `wontfix` | `wontfix` | Will not be actioned |

`to-spec` and `to-tickets` use `ready-for-agent` and `ready-for-human`. The other three are kept so a triage skill can be added later without renaming.

When a skill mentions a role, use the label string from this table.
