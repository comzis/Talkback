---
name: implement
description: "Implement one ticket from the issue tracker: branch, test first, review, and open a PR. Never merges."
disable-model-invocation: true
---

Implement one ticket, named by its issue number (`/implement 42`). Only that ticket. If no number was given, or the reference is ambiguous, ask.

## 1. Read and check

1. Read `CLAUDE.md`. Fetch the ticket with `gh issue view <N> --comments` and state its title. If it is a sub-issue of a spec, fetch the spec too (`gh issue view <spec>`): its decisions, testing decisions, constraints, and out-of-scope list bind this work.
2. Stop and tell the user if any of these is true:
   - The ticket is labelled `ready-for-human`, not `ready-for-agent`. That work is a person's to do or to check.
   - The ticket still has open blockers: `gh api repos/comzis/Talkback/issues/<N> --jq .issue_dependencies_summary.blocked_by` is not 0.
   - `git status` shows uncommitted or untracked changes, unless the ticket says they belong to it (then carry them onto the branch; never stash or discard them).
   - Another session is already working the ticket (an open PR or branch for it exists).
3. `git checkout master && git pull`, then create `issue-<N>-<short-slug>`. Assign the ticket: `gh issue edit <N> --add-assignee @me`.

## 2. Build, test first

Call the Skill tool with "tdd". Use the seams the ticket and its spec name. For every testable criterion, write the failing test first, run it, and show it fails for the expected reason before changing app code.

If the ticket says to stop under some condition (for example, the bug turns out to be somewhere else), stop there, do what it says, and tell the user.

Run single test files as you go and the full unit loop from `CLAUDE.md` at the end:

```bash
ruff check app scripts
ruff format --check app scripts
python -m pytest
node --test app/tests/test_stream_events.mjs
```

Report the real output, not a summary of it. If a failure comes from the Claude Code sandbox (a socket-bind `PermissionError`, a TLS error from `gh`), rerun outside the sandbox and say that you did.

Don't run the live eval (`scripts/run_live_eval.py`) unless the ticket asks for it. Judging answer quality is a separate `ready-for-human` ticket.

## 3. Review

Commit to the branch, then call the Skill tool with "code-review", using `master` as the fixed point and this ticket as the spec. Its two reviews run in fresh sub-agents that did not write the code. Fix every hard finding (a broken standard or guardrail, a missing requirement), rerun the unit loop, and note what you fixed. For judgement-call findings, fix them or say in the PR why not. Refactoring happens here, not during the red → green loop.

## 4. Open the PR

Push and open a PR against `master`. The body must contain:

- `Closes #<N>`, or `Part of #<N>` when the ticket says it needs a later human check before it can close
- each acceptance criterion, with how it was checked
- the failing-then-passing test output
- the code-review summary and what was changed because of it
- anything noticed outside this ticket, mentioned, not fixed

Do not merge. Do not touch other issues. End by telling the user: the PR link, which criteria are met, and anything you're unsure of.
