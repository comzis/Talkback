# Domain docs

How the skills read this repo's domain documentation. Talkback is single-context.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root.
- **`docs/adr/`**: ADRs that touch the area you're about to work in.

Neither exists yet. If they are missing, proceed silently. `/grill-with-docs` creates them through the `domain-modeling` skill when a term or a decision is actually settled.

The other files in `docs/` (`SECURITY.md`, `status-db.md`, `memory.md`, `server-setup.md`, `eval-authoring.md`, `pilot-corpus.md`, `adding-a-source.md`) describe how the system runs today. Read the one that matches the area you touch. `docs/archive/` describes an older setup; do not treat it as current.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary avoids.

If the concept you need isn't in the glossary yet, either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, say so explicitly rather than silently overriding:

> _Contradicts ADR-NNNN (<its title>), but worth reopening because…_
