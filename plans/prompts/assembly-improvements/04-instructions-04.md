# INSTRUCTIONS-04 — Fix Floor review and local skill instructions

Open a fresh session in `/home/ned/ai/assembly-floor`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-5.6-luna
- Harness/rail: Codex / subscription
- Effort: high
- Why: Bounded requirements, named file ownership and verifiable acceptance fit this execution role; subscription evidence permits a bounded attempt.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: deepseek/deepseek-v4-flash-0731 / OpenRouter / high; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only INSTRUCTIONS-04: Fix Floor review and local skill instructions.

Repository: Design-Machines-Studio/assembly-floor
Checkout for discovery: /home/ned/ai/assembly-floor
Prepared exact base (2026-09-08): 561352882d2402ffb2b6889de101f31c22e0ef8b
Owning plugin: none; repository-owned instructions/workflow
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: high

Prerequisite and collision boundary:
Run after INSTRUCTIONS-01 has merged. Fetch Design-Machines-Studio/depot main read-only using /home/ned/ai/depot and inspect the exact merged project-scaffolder source and root guidance through Git, without modifying its primary checkout or relying on stale installed templates. If the prerequisite is absent, complete only the read-only mapping and report the blocker. Floor PR #6 is active at a466d2ff960b385a5e9a6061678676444b8511de. Both /home/ned/ai/assembly-floor and /home/ned/assembly/assembly-floor exist; preserve both and use a fresh worktree.

Workspace:
Use /home/ned/ai/assembly-floor only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/assembly-floor-worktrees and a new branch named docs/instructions-04 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Inspect tracked AGENTS.md/CLAUDE.md and all local skill/hook/agent instruction surfaces. Correct the rule making retained P3 findings advisory: every retained P1/P2/P3 must be fixed and verified before merge, while unsupported findings should be dismissed explicitly. Make personal design memory optional. Remove any local blanket chores conflicting with the reviewed shared defaults.

Preserve Floor as a read-only progress/evidence consumer, its exact source/provenance rules, and Live Wires/design authority. Do not add execution controls, a task broker, an alternative work store, or changes to PR #6's Foreman-reader code.

Acceptance and focused verification:
No local instruction allows deferring a retained P3. The workflow works without personal systems and still prohibits product writes outside Floor's read-only boundary. Verify the changed instruction scopes and links; use affected hook fixtures only if hooks changed.

Consumer canary:
Walk one retained P3 and one unavailable evidence source through the revised rules, without presenting missing evidence as a clean result.

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
