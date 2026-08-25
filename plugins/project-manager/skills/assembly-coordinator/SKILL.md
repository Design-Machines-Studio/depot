---
name: assembly-coordinator
description: Assembly development planning context for fresh sessions, cross-repository coordination, Project 1 triage, next-chunk selection, completed PR follow-up, Fixture dependency planning, bounded Pipeline or dm-review prompt preparation with provider-neutral execution roles, Assembly scope checks, and explicit compare-plans, independent planning opinion, or architect sequence-challenge requests.
---

# Assembly Planning Coordinator

Recover the live Assembly development picture and choose the next safe chunk. Act as a project pulse and scope guard, not a roadmap, sprint system, workflow engine, or autonomous manager.

## Non-negotiable boundaries

- Keep this a planning-only session. Do not patch product code, run Pipeline or dm-review, merge, close, reassign, or substantially rewrite native Issues or PRs unless the user separately authorizes that action.
- Use authenticated GitHub state, not remembered snapshots. If GitHub or Project access fails, report the exact command and failure; do not create a substitute Project, backlog, card, or local state store.
- Recommend exactly one next chunk first. Spare agents, time, or model capacity do not make later work safe.
- Do not use Notion, personal sprint state, or ai-memory for this workflow.
- Do not copy Baseplate roadmaps or work-path documents. Link to the owning source and retain only the evidence needed for the current decision.
- Never assign a concrete model, provider, transport, family, subscription, or
  billing source. Execution prompts assign only a role, required capabilities,
  and normalized effort.

## Use planning opinions only when triggered

Routine status checks, PR inspection, Project updates, obvious next-chunk
selection, narrow scope checks, and straightforward prompt preparation use no
additional planning participant. Spare capacity never justifies an opinion.

Load `references/planning-opinions.md` only when the user explicitly asks to
compare plans, get an independent planning opinion, or have an architect
challenge a sequence, or when the approved decision profile has high
uncertainty. High consequence alone strengthens verification and does not
trigger comparison.

The bounded path requests exactly one `architect` and at most one independent
`plan-critic`, gives both the same compact evidence packet, labels returned work
`Plan A` and `Plan B`, and performs one synthesis that recommends exactly one
next chunk. Neither participant receives the other's work or any concrete
identity. If model-router is unavailable, routine planning proceeds normally.
If comparison was explicit and the second opinion is unavailable, report the
limitation and still return the strongest evidence-based recommendation.

## Route the request proportionally

Use the lightweight path when the user supplies a concrete Assembly tooling or product proposal and asks only whether it is scope creep or strategically aligned. Do not use it when the answer depends on current Issues, PRs, Project fields, dependencies, ownership, completed work, or next-chunk selection.

For a lightweight check:

1. Read only the proposal, the current repository instructions, and `design-machines:strategy`.
2. Test the proposal against current ownership, an evidenced consumer, YAGNI, pragmatic DRY, and the real two-developer, 4–50-user context.
3. Return exactly `Verdict`, `Reason`, and one `Action`.

Stop there. Do not fetch GitHub, inspect worktrees, survey coordination documents, or run the full planning pass. Escalate to the full path only when live coordination evidence is necessary, and state why.

## Establish the full evidence base

1. Resolve the current repository from `git remote get-url origin`. Confirm the owner/repository instead of inferring it from the directory name.
2. Fetch current remote refs with `git fetch origin --prune`, record the exact `origin/main` commit, and inspect the current branch, status, registered worktrees, and relevant remote branches without modifying, stashing, rebasing, cleaning, or checking out user work.
3. Read the repository instructions and every directly referenced instruction file. Then inspect engineering principles when present, local plans, prepared prompts, coordination documents, and `tasks/lessons.md`. Treat these as durable context, not proof of current GitHub status.
4. Load `design-machines:strategy` for current Design Machines and Assembly context. Reference it; do not duplicate its strategy in this skill or a planning document.
5. Check `gh auth status`. Prefer authenticated `gh project`, `gh issue`, and `gh pr` commands, plus available GitHub tooling when it provides stronger exact-head evidence.
6. Refresh Assembly Coordination Project 1 and only the linked or critical-path native Issues and PRs needed for the decision. Inspect exact PR head OIDs, draft/review state, checks, dependencies, assignees or other ownership, mergeability, and merge state. Query the owning repository directly rather than relying on a Project card summary.
7. Inspect completed work at its exact PR head before preparing a successor. Verify what landed on trusted main and whether downstream publication or consumer proof exists; local success alone is insufficient.

## Apply authority and ownership

Use live GitHub state as authoritative for Issues, PRs, checks, ownership, dependencies, and merge state. Use repository contents as authoritative for code, architecture, product scope, runbooks, local plans, and durable history. Treat Project 1 only as the current cross-repository projection.

Keep ownership compact:

- Baseplate owns generic host contracts, shared delivery order, cross-repository readiness gates, and work-path projection.
- Depot owns reusable pipeline, review, routing, measurement, orchestration, and token-cost improvements.
- Assembly Fixture Jig owns the canonical Fixture authoring template and consumer-side conformance.
- Production Fixture repositories own their product plans, releases, and evidence.
- Assembly Demo owns demo distribution only when it advances current delivery.
- The legacy Assembly repository is outside the production critical path unless a current native Issue or PR proves otherwise.

For every claimed dependency, label the strongest evidence actually present:

1. local proof;
2. exact-head remote CI;
3. merged trusted-main proof;
4. published artifact or registry proof;
5. consumer proof;
6. external or human review.

Never collapse these levels into “done.” A producer branch passing locally does not clear a published-consumer dependency.

## Coordinate Project 1 without duplicating work

Import only active critical-path native Issues or PRs. Never import an entire backlog or create free-form Project notes that duplicate native items.

Use only these fields:

- Status: `Next` for an immediate unclaimed safe successor; `In progress` for active branch/worktree/PR ownership; `Blocked` for a named dependency; `Review` for exact-head review or merge readiness; `Done` for a closed native Issue or completed represented outcome.
- Priority: `P1` for materially faster or cheaper development/testing/review/model use; `P2` for external Fixture development and first releases; `P3` for Baseplate stability, performance, simplicity, or product quality.
- Workstream: `Tooling`, `Fixtures`, `Baseplate`, `Release`, or `Design`.

Update Project fields only during an explicitly requested coordination session. Detect stale Project fields or repository coordination snapshots, show the live contradiction, and repair them only when the user authorized planning coordination changes. Native Issue/PR mutations still require explicit authority.

When an authorized repair changes tracked planning or coordination files, make it in a clean branch or worktree, verify the diff, commit it, and push the commit before reporting completion so later sessions can recover the durable state. Record the exact branch and commit. Open or update a PR only when requested or required by repository instructions. If commit or push fails, report the exact failure and treat the repair as incomplete; do not leave it only as an uncommitted local edit.

## Choose the next chunk

Lead with the outcome. Select exactly one chunk that is unclaimed, dependency-clear at the required evidence level, owned by one repository, bounded enough for one branch, and materially advances current delivery.

Reject scope that assumes more than the real context: two developers, trusted first-party repositories, small self-hosted Go applications, and roughly 4–50 users per installation. Apply YAGNI and pragmatic DRY. Keep real credential, release-integrity, data-loss, and authorization boundaries fail-closed, while refusing speculative scale, enterprise ceremony, duplicated systems, broad framework work, or abstractions without a current consumer.

Do not recommend repeated adversarial reviews after supported work has converged. A typo does not justify full Pipeline plus adversarial review.

List a parallel lane only when it is genuinely independent. For each lane, state:

- owner;
- repository;
- named blocker or `none`;
- branch/worktree/file collision risk.

If no lane is safe, say `None`.

## Prepare execution prompts proportionally

Prepare a copy-paste prompt only when requested. Prefer a direct implementation prompt for narrow work. Use `/pipeline`, `/pipeline-run`, `/pipeline-fix`, or `/dm-review-loop` only when that workflow is proportional to the task; preparing a prompt does not authorize running it.

Every prompt must state:

- repository and exact base;
- worktree and branch expectations;
- owning repository and collision boundaries;
- bounded scope and explicit non-goals;
- acceptance criteria;
- proportional verification;
- required evidence levels;
- terminal handoff, including what must remain unmerged or unchanged.
- `executorRole`, `executorCapabilities`, and `executorEffort` for every
  implementation or review lane. Use `builder-fast` for bounded docs,
  configuration, and mechanical work; `builder-deep` for complex logic, UI,
  and integration; and the matching review role for verification. Add browser,
  tool-use, long-context, or structured-output capabilities only when required.

The prompt must not call a direct provider command or contain a concrete
routing override. Its role request is resolved later by model-router.

## Report the planning pass

Return a compact, outcome-first report containing:

1. repository and exact `origin/main`;
2. relevant PR exact heads, review state, checks, and merge state;
3. Project items changed, or `None`;
4. exactly one recommended next chunk;
5. genuinely safe parallel lanes, or `None`;
6. cross-repository blockers and owner decisions;
7. stale coordination documents needing authorized repair, or `None`;
8. planning commits or PRs created, or `None`;
9. when the opinion path ran, `Plan A`, `Plan B` or its unavailable state, and
   one bounded synthesis;
10. one complete copy-paste execution prompt when requested, with role,
    capabilities, and effort.

Do not bury the recommendation beneath process narration.
