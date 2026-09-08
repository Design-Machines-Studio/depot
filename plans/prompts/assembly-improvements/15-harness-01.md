# HARNESS-01 — Prove the current Pi adapter and remove the blocking proof assumptions

Open a fresh session in `/home/ned/ai/foreman`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-6-astra
- Harness/rail: Codex / subscription
- Effort: medium
- Why: The task requires actual Pi/tool integration and failure diagnosis; medium effort with native host tools is proportional.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: gpt-5.6-sol / Codex / medium; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only HARNESS-01: Prove the current Pi adapter and remove the blocking proof assumptions.

Repository: Design-Machines-Studio/foreman
Checkout for discovery: /home/ned/ai/foreman
Prepared exact base (2026-09-08): 8234aeb73aa76b7f084572f3fcd52ca54acbffdc
Owning plugin: none; repository-owned instructions/workflow
executorRole: builder-deep
executorCapabilities: ["read-repository", "write-repository", "structured-output", "long-context", "tool-use"]
executorEffort: medium

Prerequisite and collision boundary:
Run after INSTRUCTIONS-06 and current routing guidance are available. Recheck Floor PR #6 and all Foreman worktrees; keep changes in Foreman and hand off Floor-specific UI work.

Workspace:
Use /home/ned/ai/foreman only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/foreman-worktrees and a new branch named docs/harness-01 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Inspect package.json, src/pi-session.mjs, the current proof manifest/model binding, session events and tests. The audit at this base found Pi 0.84.4, fixed high thinking, disabled compaction and an in-memory/fixed proof task. Reverify each; do not assume the adapter is broken.

First run one bounded task through the actual existing Pi adapter and verify tool-request compatibility, requested/served participant evidence, effort, progress, steering and cancellation. Read current primary provider/Pi documentation only for the actual adapter. Preserve native subscription/provider boundaries; do not route OpenAI or Anthropic through an unauthorized API rail.

Then change only fixed task/effort assumptions that demonstrably prevent current development, using one current work profile and Pi's existing event/steer/abort facilities. Keep context/compaction as a separately measured option. Do not build a broker, alternate workflow engine, general transport service or new Floor write controls. If tool transport is unavailable, return exact reproducible evidence and an ownership-correct handoff rather than fabricating a pass.

Acceptance and focused verification:
One real bounded task can be followed, steered and stopped through the current path, with honest model/effort/usage gaps. Focused adapter tests cover changed behavior and failure handling. Preserve repository-owned verification and record actual commands. No project-wide dependency upgrade without a demonstrated adapter requirement. OpenRouter continuation must use only the existing adapter's real capabilities and stay within the common cap.

Consumer canary:
A small read-only repository analysis using an actual tool call, followed by one bounded approved write only if necessary to verify the existing development path. Keep tests of steering/cancellation disposable and cleanup owned resources only.

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
