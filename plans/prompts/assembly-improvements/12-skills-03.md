# SKILLS-03 — Reduce repeated dm-review instructions without losing detection

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
Implement only SKILLS-03: Reduce repeated dm-review instructions without losing detection.

Repository: Design-Machines-Studio/depot
Checkout for discovery: /home/ned/ai/depot
Prepared exact base (2026-09-08): 386b98e26f493cc220047c981cd5c01b1513b24d
Owning plugin: dm-review
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: high

Prerequisite and collision boundary:
Run after INSTRUCTIONS-01 is merged and the relevant consumer authority can be read at a current exact commit. Review the latest preceding result before starting; this is a reserved later prompt, not authorization to run all plugin passes together. Wait until PR #129 or its explicit successor has finished the shared review/browser surfaces. Reuse its completed browser proof when still exact; do not become a second writer.

Workspace:
Use /home/ned/ai/depot only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/depot-worktrees and a new branch named docs/skills-03 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Own affected canonical plugins/dm-review review skills, commands, references and fixtures. Consolidate duplicated instructions and shorten entrypoints through task-specific references. Fix only demonstrated conflicts or repeated work.

Preserve all applicable lanes, every retained P1/P2/P3, convergence rules, origin-neutral review, role routing, actual cost/model reporting, repository-owned target discovery, exact-head browser evidence, T3-first automation and cleanup of review-created resources only. Use existing runbooks before declaring unavailable coverage. Never turn a skipped lane into a clean pass. No new browser broker, service, runbook parser, review fan-out, or evidence ledger.

Acceptance and focused verification:
Existing lane-selection, finding, terminal, browser-readiness/discovery and cleanup fixtures remain green. An ordinary converged review does not add another full suite. Report loaded bytes and any remaining gaps honestly. Regenerate aliases for changed canonical commands and run full composition.

Consumer canary:
Reuse the exact compatible Jig desktop/mobile evidence from UI-READY when unchanged; otherwise rerun only the affected declared browser path. Source-only wording changes need no invented new browser campaign.

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
