---
name: to-spec
description: "Turn the current conversation into a spec and publish it as a GitHub issue on comzis/Talkback: no interview, just synthesis of what you've already discussed."
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user; just synthesize what you already know.

Read `docs/agents/issue-tracker.md` for how to publish, and `docs/agents/triage-labels.md` for the label strings.

The spec lives on the issue tracker, not in the repo. Do not write it to a file under `docs/`: plans in the tree go stale and later sessions treat them as current.

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the spec, and respect any ADRs in the area you're touching (see `docs/agents/domain.md`).

2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

   Talkback has two feedback loops. Say which one each seam belongs to:

   - **Unit loop.** `python -m pytest`, `ruff check app scripts`, `ruff format --check app scripts`, `node --test app/tests/test_stream_events.mjs`. Runs offline, with no model and no Chroma. An agent can run it on its own.
   - **Answer loop.** `scripts/run_live_eval.py` against a running stack with Ollama and the cached models. It measures retrieval, citations, and reply language. An agent on the Mac may run it and report the numbers before and after; a person judges the result before merge.

   If the change can alter what a user gets back for a library question (retrieval, rerank, prompts, citation checks, language handling), say so plainly and name the eval cases that are the evidence. New eval rows are written by engineers from the documents, following `docs/eval-authoring.md`; the spec may say rows are needed, but never drafts expected answers.

Check with the user that these seams match their expectations.

3. Write the spec using the template below, then publish it to the project issue tracker. Apply the `ready-for-agent` triage label - no need for additional triage.

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As an engineer searching the library, I want each cited claim to show its file and page, so that I can check the source before I rely on the answer
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested, and through which loop (unit or answer)
- Prior art for the tests (i.e. similar types of tests in the codebase)
- For answer-loop changes: which existing eval cases are the evidence, and whether engineers need to write new rows

## Constraints

Anything from `docs/SECURITY.md` or the README that this change must keep: documents and answers stay on the machine, `OFFLINE_MODE` blocks outbound calls, ports stay on loopback, pilot models are Apache 2.0 or MIT. Write "None touched" if the change is clear of all of them.

## Out of Scope

A description of the things that are out of scope for this spec.

## Further Notes

Any further notes about the feature.

</spec-template>
