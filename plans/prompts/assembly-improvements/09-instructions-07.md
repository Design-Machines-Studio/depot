# INSTRUCTIONS-07 — Verify Demo instructions without inventing work

Open a fresh session in `/home/ned/assembly/assembly-demo`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-5.6-luna
- Harness/rail: Codex / subscription
- Effort: low
- Why: This is a small instruction/discovery change with clear acceptance; low effort is proportional.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: deepseek/deepseek-v4-flash-0731 / OpenRouter / low; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only INSTRUCTIONS-07: Verify Demo instructions without inventing work.

Repository: Design-Machines-Studio/assembly-demo
Checkout for discovery: /home/ned/assembly/assembly-demo
Prepared exact base (2026-09-08): c7a54d5f2005edf0e7e4b5d10fdb4eb66286f200
Owning plugin: none; repository-owned instructions/workflow
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: low

Prerequisite and collision boundary:
Run after INSTRUCTIONS-01 has merged. Fetch Design-Machines-Studio/depot main read-only using /home/ned/ai/depot and inspect the exact merged project-scaffolder source and root guidance through Git, without modifying its primary checkout or relying on stale installed templates. If the prerequisite is absent, complete only the read-only mapping and report the blocker. No Demo PR was open at preparation.

Workspace:
Use /home/ned/assembly/assembly-demo only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/assembly/assembly-demo-worktrees and a new branch named docs/instructions-07 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
The audit found a thin AGENTS.md and no demonstrated model-specific defect. Verify current tracked instructions and any repository-owned skills/hooks against the reviewed shared policy. Correct only actual contradictions or missing necessary portable authority.

Preserve stock factory-install/distribution ownership, configuration and release requirements. Do not add product features, a second roadmap, a new model policy or a duplicate CLAUDE guide solely to mention the new driver. A no-change result is valid.

Acceptance and focused verification:
Record inspected instruction/local-skill paths and any actual conflicts. If changed, verify loading/links and affected hooks. If already aligned, leave the repository unchanged and explain the concrete evidence; no empty commit or PR.

Consumer canary:
Confirm a fresh session can identify the stock-install verification authority without personal systems or unrelated product work.

Working constraints:
Build for two trusted developers and self-installed, federated co-op intranets of 5–50 people with trusted internal Fixtures. Apply YAGNI, pragmatic DRY, Live Wires/component reuse, accessibility, performance and maintainability. Preserve real authorization, credential, data-loss and release protections. No enterprise infrastructure. The driver retains design/integration/final acceptance; workers get bounded ownership. Route only role/capabilities/effort, with no concrete identities in participant packets or automatic inheritance of driver/max effort.

Use a direct, proportionate workflow and reuse still-exact evidence. No automatic full Pipeline/adversarial suite for instruction edits. Fix every retained P1/P2/P3 and verify affected behavior; stop review churn after convergence. Routine implementation choices are yours; ask only for a real missing decision or authorization.

Economics:
Refresh installed routing/matrix evidence before dispatch. Prefer eligible subscriptions and useful bounded OpenRouter offload. Paid calls have a $0.25 total ceiling, subject to known remaining monthly budget; $50/month is a goal, not verified headroom. Use deterministic checks where sufficient. Respect real export restrictions; report unavailable lanes and distinguish fixtures from actual calls.

Version and generated surfaces:
Instruction-only consumer changes normally require no application version bump, release tag or plugin-cache synchronization. Follow the owning repository's actual policy if runtime hooks change. Preserve generated code and vendored/shared plugin content. Run repository-appropriate focused checks; do not run Depot composition for a consumer that contains no Depot plugin change. Hand off a discovered shared-plugin defect to its exact Depot owner instead of patching a cache.

GitHub and delivery:
Verify, commit, push and open a proper PR to main with this task ID in its title, final behavior and evidence gaps. If already satisfied, report evidence without an empty commit/PR. Do not mutate native Issues, merge, tag or refresh installations. Changed plugins still need separately authorized publication, both-cache synchronization and real installed consumer proof.

Use only Assembly Coordination Project 1: the relevant created PR is Review / P1 / Tooling, or Blocked with its real dependency. No duplicate backlog. CLEANUP-01 remains an inventory PR only.

Treat 40 tool calls as an exploration checkpoint; finish authorized repairs, verification, commit, push and PR creation. Keep updates brief.

Final report:
Report result, exact base/head, changes, actual checks, PR/Project state, delivery level and one next action. For routed work, report role, attempted/served participant, rail, effort, duration, outcome, measured tokens/cost, subscription calls, fallbacks and unavailable measurements. Finish with SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
```
