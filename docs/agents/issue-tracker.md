# Issue tracker: GitHub

Specs and tickets for this repo live as GitHub issues on `comzis/Talkback`. Use the `gh` CLI for all operations. File issues only into this repo. Before the first `gh issue create` of a session, check the target with `gh repo view --json nameWithOwner`.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --json number,title,body,labels,comments`.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with `--label` and `--state` filters as needed.
- **Make an issue a sub-issue of a parent**: `gh issue create --parent <parent> ...`, or `gh issue edit <parent> --add-sub-issue <child>` afterwards (`gh` 2.94+). Older `gh`: `gh api --method POST repos/comzis/Talkback/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`. Without sub-issues, put `Part of #<parent>` at the top of the child body.
- **Blocking**: GitHub's native issue dependencies. Add an edge with `gh issue create --blocked-by <n>,<n> ...` or `gh issue edit <child> --add-blocked-by <blocker>` (`gh` 2.94+). Older `gh`: `gh api --method POST repos/comzis/Talkback/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric database id (`gh api repos/comzis/Talkback/issues/<n> --jq .id`, not the `#number`). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Count open blockers**: `gh api repos/comzis/Talkback/issues/<n> --jq .issue_dependencies_summary.blocked_by` (0 means startable).
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: post the explanation with `gh issue comment <number> --body "..."`, then `gh issue close <number>`.

Check `gh --version` once per session. The 2.94+ flags above fail on older versions; use the `gh api` form instead.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Closed specs

A shipped spec stays as a closed issue. Do not copy it into the repo. Read the code, `GLOSSARY.md`, and `docs/adr/` for the current state, not old specs.
