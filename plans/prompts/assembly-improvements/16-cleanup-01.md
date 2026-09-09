# CLEANUP-01 — Prepare the exact workspace cleanup inventory

Open a fresh session in `/home/ned/ai/depot`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-6-astra
- Harness/rail: Codex / subscription
- Effort: low
- Why: The task requires actual host filesystem or release tools; low effort on the native driver is sufficient for this bounded procedure.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: gpt-5.6-sol / Codex / low; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only CLEANUP-01: Prepare the exact workspace cleanup inventory.

Repository: Design-Machines-Studio/depot
Checkout for discovery: /home/ned/ai/depot
Prepared exact base (2026-09-08): 386b98e26f493cc220047c981cd5c01b1513b24d
Owning plugin: none; repository-owned instructions/workflow
executorRole: builder-deep
executorCapabilities: ["read-repository", "write-repository", "structured-output", "tool-use"]
executorEffort: low

Prerequisite and collision boundary:
Read-only inventory may run independently. This prompt authorizes no deletion, worktree removal, branch deletion, permission changes, stash/reset/clean or process termination.

Workspace:
Use /home/ned/ai/depot only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/depot-worktrees and a new branch named docs/cleanup-01 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

GitHub availability: use authenticated REST if GraphQL or a gh command is rate-limited. A missing Project item or unavailable Project API does not block repository edits, tests, commits, push or a PR. Use Git refs and available repository API evidence; mark unavailable coordination explicitly. If PR creation itself is unavailable, finish safe isolated work and push when Git transport works, then report PR creation pending rather than claiming completion. Do not treat the mere existence of an unrelated PR as a file collision.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Inventory /home/ned/ai and /home/ned/assembly using existing Git/filesystem tools. Identify primary clones, registered worktrees, independent clones, upstream references, dependency caches and historical proof directories. Record exact branch/head, dirty/untracked state, remote reachability, unique commits/files, linked PR state and evidence ownership for candidate cleanup paths. Do not treat every AGENTS copy as a separate project.

Write a compact keep/archive/remove-candidate/uncertain report under plans/workspace-cleanup/ in this fresh Depot branch. Preserve protected/unreadable directories as uncertain without changing permissions. Do not include credentials, raw private content, environment files or authentication material in the report.

Prepare an exact proposed removal list with why each item is recoverable, where unique evidence will be retained, and the checks to repeat immediately before deletion. Stop at a reviewable inventory PR. Actual deletion requires a later complete prompt bound to the approved list; do not substitute broad globs, age rules or a new cleanup registry/service.

Acceptance and focused verification:
Every proposed path has an exact ownership/recovery reason and current Git evidence; active and unique work is kept. Record unreadable scope explicitly. No destructive command runs. Check report links, machine-readable data if used, and diff hygiene; no plugin/application test suite is needed for the inventory.

Consumer canary:
Recheck two representative keep/remove-candidate classifications against Git without deleting anything. The final next action is review the exact list, not execute cleanup.

Working constraints:
Build for two trusted developers and self-installed, federated co-op intranets of 5–50 people with trusted internal Fixtures. Apply YAGNI, pragmatic DRY, Live Wires/component reuse, accessibility, performance and maintainability. Preserve real authorization, credential, data-loss and release protections. No enterprise infrastructure. The driver retains design/integration/final acceptance; workers get bounded ownership. Route only role/capabilities/effort, with no concrete identities in participant packets or automatic inheritance of driver/max effort.

Use a direct, proportionate workflow and reuse still-exact evidence. No automatic full Pipeline/adversarial suite for instruction edits. Fix every retained P1/P2/P3 and verify affected behavior; stop review churn after convergence. Routine implementation choices are yours; ask only for a real missing decision or authorization.

Economics:
Refresh installed routing/matrix evidence before dispatch. Prefer eligible subscriptions and useful bounded OpenRouter offload. Paid calls have a $0.25 total ceiling, subject to known remaining monthly budget; $50/month is a goal, not verified headroom. Use deterministic checks where sufficient. Respect real export restrictions; report unavailable lanes and distinguish fixtures from actual calls.

Version and validation:
This is a planning/inventory diff: no plugin or application version movement, generated-file changes, full application suite or cache operation. Validate the report and Git evidence. If current source has a reusable exact composition result, cite it only as source evidence, not as an inventory test.

GitHub and delivery:
Verify, commit, push and open a proper PR to main with this task ID in its title, final behavior and evidence gaps. If already satisfied, report evidence without an empty commit/PR. Do not mutate native Issues, merge, tag or refresh installations. Changed plugins still need separately authorized publication, both-cache synchronization and real installed consumer proof.

Use only Assembly Coordination Project 1: the relevant created PR is Review / P1 / Tooling, or Blocked with its real dependency. No duplicate backlog. CLEANUP-01 remains an inventory PR only.

Treat 40 tool calls as an exploration checkpoint; finish authorized repairs, verification, commit, push and PR creation. Keep updates brief.

Final report:
Report result, exact base/head, changes, actual checks, PR/Project state, delivery level and one next action. For routed work, report role, attempted/served participant, rail, effort, duration, outcome, measured tokens/cost, subscription calls, fallbacks and unavailable measurements. Finish with SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
```
