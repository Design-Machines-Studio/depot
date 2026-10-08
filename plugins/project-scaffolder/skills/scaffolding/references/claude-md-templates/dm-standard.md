<!--
Behavioural principles below paraphrase Andrej Karpathy's observations on LLM coding
pitfalls (https://x.com/karpathy/status/2015883857489522876).
-->

# CLAUDE.md

This file tells Claude Code how to work in this repository. Read it at the start of every session.

## Workflow and Safety

- Choose the lightest workflow that fits the task. A small documentation, configuration, or bounded content edit needs focused verification, not plan mode, a full pipeline, or an automatic agent roster.
- Use plan mode when work is multi-step, architectural, cross-cutting, or higher risk and a written sequence clarifies the acceptance criteria.
- Use focused agents only when their checks apply. Update documentation when behavior, commands, setup, or operating instructions change; record lessons only when a finding is reusable beyond this task.
- Preserve repository-owned command restrictions and real checks for credentials, authentication/authorization, destructive or data-loss actions, release integrity, and applicable accessibility.
- Keep ordinary source-branch commits/pushes, release publication, and any post-publication verification separate. Follow the project's documented release checks when publishing; do not treat an unreleased source branch as a published release.
- When delegating, request only a role, required capabilities, and normalized effort (`low`, `medium`, `high`, or `max`). Keep concrete model and rail recommendations in human-facing operator context; see the [current model-router guidance](https://github.com/Design-Machines-Studio/depot/blob/main/plugins/model-router/skills/model-router/references/driver-worker-guidance.md).

## How to Work Here

### 1. Think before coding

Don't assume silently. When the task admits more than one reasonable interpretation, name them before touching code and choose one with a stated rationale. If you are confused, say what is confusing and ask -- don't paper over it with plausible-looking output. A clarifying question up front is cheaper than a rewrite after.

### 2. Simplicity first

Write the minimum code that satisfies the request. No speculative features, no abstractions for single-use code, no configurability nobody asked for, no error handling for scenarios that cannot occur. If a senior engineer would call the result overcomplicated, it is overcomplicated -- rewrite it shorter.

### 3. Surgical changes

Every line you change must trace directly to the request. Don't improve adjacent code, don't reformat, don't rewrite comments, don't tighten types on lines you weren't already touching. If you notice unrelated issues in a file you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.

### 4. Goal-driven execution

Turn every task into a verifiable outcome before you start. "Make it work" is not a goal; "the login form accepts valid credentials and rejects invalid ones, with passing tests" is. State the success criterion, implement, verify. Loop only against a concrete criterion, never against vibes.

## Design Machines Conventions

### Live Wires CSS

This project uses the [Live Wires CSS framework](https://github.com/Design-Machines-Studio/live-wires) -- cascade layers, baseline rhythm tokens, container queries, editorial-first primitives. Use the existing primitives and utilities. Do not invent new class names when a token or primitive already covers the need.

### Proportional review

After plan/prompt approval, implement and commit/push the candidate branch.
Use dm-review's `automatic-implementation-closeout.md`: independently review,
fix every retained P1/P2/P3 defect, reject unsupported preferences with reasons,
recheck affected evidence and preserve source/browser proof before opening a PR.
Direct tasks use one supported loop; Pipeline uses its single integrated owner
and final review. A repair push never starts a duplicate broad review.

Use `publish-reviewed-pr.sh` for both PR creation and draft-to-ready transitions
with the exact automatic-closeout arguments; never bypass it with bare `gh`.
PR-only CI remains pending until the PR exists. Keep the draft until actual
final-head automation, independently settled feedback and required designer UI
acceptance pass. At an unchanged covered head with zero findings, wait for CI/
feedback without reviewer dispatch. Use chunk01's `operator-handoff.sh` human
handoff for browser tasks and owner merge; never ask for routine backend-code
review or PR creation. Preserve planning and material-scope approval.

Generate `noMergeOnCompletion=true`; missing or false legacy controls never
authorize agent merge. Only the root owner binds the exact native SessionStart
context after approval and updates actual phases with `review-owner-context.sh`;
workers receive the ref read-only. When hooks are unavailable, report
`hook activation unavailable` and still run the mandatory pre-PR producer gate.
No agent merges, tags or releases by implication.

### Brainstorm trigger

Route creative UI and design work through the brainstorming skill before implementation. Triggers include phrases like "brainstorm," "explore ideas," "reimagine," "let's try," and any new visual layout or page design decision. Routine changes -- adding a column, fixing a label, wiring an existing pattern -- skip brainstorming.

### Install the depot

Most DM tooling lives in the depot marketplace. Install it in Claude Code:

```shell
/plugin marketplace add Design-Machines-Studio/depot
/plugin install <plugin-name>@depot
```

Relevant plugins for this project: `dm-review` (code review orchestrator), `live-wires` (CSS framework skill), `pipeline` (feature development pipeline), and the accessibility reviewers under `accessibility-compliance`.

## Project-Specific Rules

<!-- Replace this section with rules unique to this repository: build commands,
     deployment targets, naming conventions, architectural invariants, etc.
     Keep it short -- one line per rule where possible. -->
