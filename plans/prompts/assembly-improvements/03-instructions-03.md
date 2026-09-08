# INSTRUCTIONS-03 — Make prototype instructions portable and proportional

Open a fresh session in `/home/ned/assembly/assembly`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-5.6-luna
- Harness/rail: Codex / subscription
- Effort: high
- Why: Bounded requirements, named file ownership and verifiable acceptance fit this execution role; subscription evidence permits a bounded attempt.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: deepseek/deepseek-v4-flash-0731 / OpenRouter / high; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only INSTRUCTIONS-03: Make prototype instructions portable and proportional.

Repository: Design-Machines-Studio/assembly
Checkout for discovery: /home/ned/assembly/assembly
Prepared exact base (2026-09-08): 4f811431a970cd6b6ac82ed762a707ccc01b9887
Owning plugin: none; repository-owned instructions/workflow
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: high

Prerequisite and collision boundary:
Ready independently. INSTRUCTIONS-01 is a Depot generator task, not a consumer prerequisite. PR #132 contains these prompts, not the generator implementation. Neither PR needs to merge for this repository-owned repair; no new plugin API, generated artifact, tag or cache installation is required. Apply the agreed policy in this packet and preserve current repository engineering contracts. Read newer Depot source as optional comparison evidence when useful; do not search for a prerequisite merge as a gate. Check actual file ownership before writing. A dirty primary checkout or missing task branch is not a blocker: create the fresh worktree described below. If this task is already implemented, verify and report it rather than repeating it.

Agreed policy for this task: select planning and verification by the actual task and risk, not file count; remove automatic documentation-agent, lesson-update and repeated approval chores; keep personal systems optional; use short shared authority with task-specific references. Preserve real security/release boundaries, all retained P1/P2/P3, repository commands, accessibility, performance, component reuse and applicable prototype/browser evidence. This policy is sufficient to implement the local repair without waiting for a generator change. Prototype PR #118 is active at ec217706e50ef6779f31a59671f28c64643cd7ae; avoid its Atlas product files.

Workspace:
Use /home/ned/assembly/assembly only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/assembly/assembly-worktrees and a new branch named docs/instructions-03 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

GitHub availability: use authenticated REST if GraphQL or a gh command is rate-limited. A missing Project item or unavailable Project API does not block repository edits, tests, commits, push or a PR. Use Git refs and available repository API evidence; mark unavailable coordination explicitly. If PR creation itself is unavailable, finish safe isolated work and push when Git transport works, then report PR creation pending rather than claiming completion. Do not treat the mere existence of an unrelated PR as a file collision.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Inspect tracked instruction scopes and repository-owned skills, agents, hooks and settings. The audit found mandatory personal Notion access at session start, full Pipeline selected by file count, and repeated documentation chores. Remove those prerequisites and apply the agreed policy in this packet wherever local skills/hooks reintroduce it.

Preserve this repository as the prototype UI authority. Retain exact design/component/class/copy/state expectations, Live Wires conventions, actual local development commands, and rendered desktop/mobile checks for affected UI. Do not convert prototype requirements into production Baseplate policy. Do not edit Atlas screens or absorb PR #118. No product implementation, dependency upgrade, design-system rewrite or new CI service.

Acceptance and focused verification:
A fresh session can operate with no personal Notion/memory tools. A multi-file documentation edit does not force full Pipeline. An actual rendered UI change still requires desktop/mobile evidence through repository-owned commands. Check root/local-skill links and instruction consistency, and run behavioral checks only for hooks or command paths actually changed.

Consumer canary:
Use one documentation task and one prototype UI task to demonstrate proportional instruction/verification selection; no screenshots are required for an instruction-only diff.

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
