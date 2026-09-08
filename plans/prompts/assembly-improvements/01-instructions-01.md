# INSTRUCTIONS-01 — Repair shared instruction and hook defaults

Open a fresh session in `/home/ned/ai/depot`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-5.6-luna
- Harness/rail: Codex / subscription
- Effort: high
- Why: Bounded requirements, named file ownership and verifiable acceptance fit this execution role; subscription evidence permits a bounded attempt.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: deepseek/deepseek-v4-flash-0731 / OpenRouter / high; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only INSTRUCTIONS-01: Repair shared instruction and hook defaults.

Repository: Design-Machines-Studio/depot
Checkout for discovery: /home/ned/ai/depot
Prepared exact base (2026-09-08): 386b98e26f493cc220047c981cd5c01b1513b24d
Owning plugin: project-scaffolder
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: high

Prerequisite and collision boundary:
Run first. PR #131 is merged. PR #129 remains separately owned at 07c4d5dd6a3efb0b52dc0c4df4bddd42346143dd; do not edit its dm-review or Workflow Kernel implementation.

Workspace:
Use /home/ned/ai/depot only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/depot-worktrees and a new branch named docs/instructions-01 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
The current scaffolder still mandates plan mode for small file/step counts, doc-sync and lesson chores, file-count commit reminders, and broad agent-compliance hooks. These instructions recreate the overhead we are removing.

Under plugins/project-scaffolder/skills/scaffolding/, own SKILL.md, references/project-configs.md, references/hooks.md, references/agents.md and both references/claude-md-templates starters; also own affected fixtures and Depot AGENTS.md/CLAUDE.md. Retain any mandatory starter attribution. Inspect first; change only templates and instructions that produce the demonstrated behavior.

Remove blanket plan-mode, documentation-agent, lesson-update, file-count commit, and repeated permission requirements. Use task/risk-based workflow selection, documentation when behavior or operating instructions change, and lessons only for reusable findings. Keep useful agents available without forcing them after every edit. Preserve repository-owned Docker/DDEV command restrictions, actual credential/auth/destructive-action checks, applicable accessibility review, and silence-on-pass/once-per-session reminders.

Define a proportional Depot docs-only verification path. Clarify that source-branch work and release publication have different checks: retain composition for plugin changes and release preflight for releases; do not require installed caches to equal an unreleased source branch before ordinary commit/push. Do not change the executable release preflight in this chunk.

Keep human model recommendations separate from provider-neutral role/capability/effort requests. Link to current model-router guidance instead of copying a portfolio into templates. No consumer repository edits, new framework, new default agent roster, automatic lesson store, or product code.

Acceptance and focused verification:
All four supported project types and both generic starters produce coherent portable instructions. A docs correction requires no full Pipeline or automatic agent chores; a bounded Go/Templ task has appropriate verification; an authorization/destructive-action case still retains the real boundary. Exercise changed hook behavior using temporary fixtures, including normal edits and a real denied condition. Preserve attribution and check template placeholders/links. Do not add tests that merely assert the new prose verbatim.

Consumer canary:
Generate representative instruction/hook outputs in temporary directories for the supported project types; inspect both harness entrypoints and exercise affected hooks. Record this as source/template proof. Installed consumer proof follows publication; do not overwrite an existing consumer configuration.

Working constraints:
Build for two trusted developers and self-installed, federated co-op intranets of 5–50 people with trusted internal Fixtures. Apply YAGNI, pragmatic DRY, Live Wires/component reuse, accessibility, performance and maintainability. Preserve real authorization, credential, data-loss and release protections. No enterprise infrastructure. The driver retains design/integration/final acceptance; workers get bounded ownership. Route only role/capabilities/effort, with no concrete identities in participant packets or automatic inheritance of driver/max effort.

Use a direct, proportionate workflow and reuse still-exact evidence. No automatic full Pipeline/adversarial suite for instruction edits. Fix every retained P1/P2/P3 and verify affected behavior; stop review churn after convergence. Routine implementation choices are yours; ask only for a real missing decision or authorization.

Economics:
Refresh installed routing/matrix evidence before dispatch. Prefer eligible subscriptions and useful bounded OpenRouter offload. Paid calls have a $0.25 total ceiling, subject to known remaining monthly budget; $50/month is a goal, not verified headroom. Use deterministic checks where sufficient. Respect real export restrictions; report unavailable lanes and distinguish fixtures from actual calls.

Version and composition:
Bump only changed plugins in canonical plugin and marketplace manifests, following semver. Regenerate Codex manifests and any affected command aliases; never hand-edit generated surfaces. Check dependency floors, index/graph and fixtures. Run focused tests and ./tools/validate-composition.sh --all before commit. Record source proof separately from installed behavior.

GitHub and delivery:
Verify, commit, push and open a proper PR to main with this task ID in its title, final behavior and evidence gaps. If already satisfied, report evidence without an empty commit/PR. Do not mutate native Issues, merge, tag or refresh installations. Changed plugins still need separately authorized publication, both-cache synchronization and real installed consumer proof.

Use only Assembly Coordination Project 1: the relevant created PR is Review / P1 / Tooling, or Blocked with its real dependency. No duplicate backlog. CLEANUP-01 remains an inventory PR only.

Treat 40 tool calls as an exploration checkpoint; finish authorized repairs, verification, commit, push and PR creation. Keep updates brief.

Final report:
Report result, exact base/head, changes, actual checks, PR/Project state, delivery level and one next action. For routed work, report role, attempted/served participant, rail, effort, duration, outcome, measured tokens/cost, subscription calls, fallbacks and unavailable measurements. Finish with SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
```
