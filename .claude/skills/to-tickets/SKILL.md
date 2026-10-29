---
name: to-tickets
description: Break a plan, spec, or the current conversation into tracer-bullet tickets on comzis/Talkback, each declaring its blocking edges and tagged ready-for-agent (AFK) or ready-for-human.
disable-model-invocation: true
---

# To Tickets

Break a plan, spec, or conversation into a set of **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it.

Read `docs/agents/issue-tracker.md` for how to publish, and `docs/agents/triage-labels.md` for the label strings.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a reference (a spec path, an issue number or URL) as an argument, fetch it and read its full body and comments.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Ticket titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

### 3. Draft vertical slices

Break the work into **tracer bullet** tickets.

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer it needs (sources, ingestion and store, retrieval, LLM prompts and citation checks, API, chat UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Give each ticket its **blocking edges**: the other tickets that must complete before it can start. A ticket with no blockers can start immediately.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

### 4. Tag each ticket AFK or human

A ticket is **AFK** (`ready-for-agent`) only when every acceptance criterion can be checked by the unit loop: `python -m pytest`, `ruff check app scripts`, `ruff format --check app scripts`, `node --test app/tests/test_stream_events.mjs`.

A ticket is **human** (`ready-for-human`) when any criterion needs one of these:

- Writing or reviewing eval rows (`docs/eval-authoring.md`: engineers write them from the documents)
- Accepting a `scripts/run_live_eval.py` result, or judging answer quality, citations, or reply language against a live stack (an agent may run the eval and report the numbers; a person decides)
- Anything that touches `tests/eval/heldout.json` or `tests/eval/heldout.sha256`
- Judging how the chat UI looks or feels
- Choosing or changing a chat, embedding, or rerank model (licence check on the model card)
- Host or Docker setup on a real machine (Ollama, the Mac rerank host, compose)

When a slice mixes both, split it: the AFK ticket builds and unit-tests the change, and a human ticket blocked by it runs the answer loop or the visual check.

### 5. Quiz the user

Present the proposed breakdown as a numbered list. For each ticket, show:

- **Title**: short descriptive name
- **Type**: AFK or human
- **Blocked by**: which other tickets (if any) must complete first
- **What it delivers**: the end-to-end behaviour this ticket makes work

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the blocking edges correct: does each ticket only depend on tickets that genuinely gate it?
- Is each AFK / human call right?
- Should any tickets be merged or split further?

Iterate until the user approves the breakdown.

### 6. Publish the tickets to GitHub

Publish one issue per ticket in dependency order (blockers first) so each ticket's blocking edges can reference real issue numbers. Use GitHub's native blocking relationship where the installed `gh` supports it; otherwise put a `Blocked by` section in the body (see `docs/agents/issue-tracker.md`). If the source was an existing issue, make each ticket its sub-issue. Apply `ready-for-agent` or `ready-for-human` per ticket, as agreed in step 5.

Work the **frontier**: any ticket whose blockers are all done. For a purely linear chain that means top to bottom.

Do NOT close or modify any parent issue.

<issue-template>

## Parent

A reference to the parent issue on the tracker (if the source was an existing issue, otherwise omit this section).

## What to build

The end-to-end behaviour this ticket makes work, from the user's perspective, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

## How it is checked

Unit loop, or the human check (answer loop, visual check, eval rows), and what passing looks like.

## Blocked by

- A reference to each blocking ticket, or "None (can start immediately)". Omit this section when blockers were set as native edges.

</issue-template>

Avoid specific file paths or code snippets: they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.
