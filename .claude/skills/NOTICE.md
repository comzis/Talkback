# Third-party skills

The skills in this folder are adapted from [mattpocock/skills](https://github.com/mattpocock/skills) at commit `59db609` (27 Oct 2026), under the MIT licence below. `grilling` was re-synced to commit `a496f55` (29 Oct 2026); the other skills had no upstream changes between those commits.

| Skill | Source in that repo | Changes |
| --- | --- | --- |
| `grilling` | `skills/productivity/grilling` | None (synced to `a496f55`: fact-finding sub-agents start with a fresh context window) |
| `grill-me` | `skills/productivity/grill-me` | None |
| `grill-with-docs` | `skills/engineering/grill-with-docs` | None |
| `domain-modeling` | `skills/engineering/domain-modeling` | None |
| `to-spec` | `skills/engineering/to-spec` | Points at `docs/agents/` instead of the setup skill. Names Talkback's unit loop and answer loop as test seams. Adds a Constraints section from `docs/SECURITY.md`. Keeps eval answers human-written. Talkback user-story example |
| `to-tickets` | `skills/engineering/to-tickets` | GitHub only, no local-file tracker. Talkback layers in the slice rules. New step 4: AFK (`ready-for-agent`) only when the unit loop checks every criterion; eval, held-out, UI, model choice, and host setup are `ready-for-human`. "How it is checked" section in the issue template |
| `tdd` | `skills/engineering/tdd` (`a496f55`) | `tests.md` and `mocking.md` unchanged. `SKILL.md`: seams come from the ticket and its spec's Testing Decisions instead of asking the user each time, and stop on an unplanned seam when unattended. The `codebase-design` reference is replaced by "raise interface questions on the issue". Adds Talkback's unit and answer loops, a "weakened to pass" anti-pattern, and "confirm the test fails for the expected reason" |
| `code-review` | `skills/engineering/code-review` (`a496f55`) | Specs come from GitHub issues (ticket plus parent spec), never from files in the repo. Standards always include `CLAUDE.md`, `docs/SECURITY.md` and `docs/eval-authoring.md`, plus Talkback's guardrails as hard standards. Posts the report on the PR when reviewing one, and never approves, merges or changes code. Fowler smell baseline unchanged |
| `implement` | `skills/engineering/implement` (`a496f55`) | Rewritten around the same steps (fetch the ticket, `tdd`, full suite, `code-review`, commit). Adds the checks that stop it (a `ready-for-human` label, open blockers, a dirty working tree), a branch per ticket, a PR with evidence, and never merging. No typechecking step (Python repo) |

`docs/agents/issue-tracker.md` and `docs/agents/domain.md` are adapted from that repo's `setup-matt-pocock-skills` templates. `docs/agents/triage-labels.md` keeps its five label names.

To pick up upstream changes, diff these files against a newer commit by hand. They are not updated automatically.

## Licence

MIT License

Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
