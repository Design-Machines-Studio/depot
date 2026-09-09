# SKILLS-02 — Remove duplicated Pipeline instructions and gates

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
Implement only SKILLS-02: Remove duplicated Pipeline instructions and gates.

Repository: Design-Machines-Studio/depot
Checkout for discovery: /home/ned/ai/depot
Prepared exact base (2026-09-08): 386b98e26f493cc220047c981cd5c01b1513b24d
Owning plugin: pipeline
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: high

Prerequisite and collision boundary:
This plugin pass does not depend on the generator or consumer instruction PRs merging. Use the policy in this packet and read the current relevant consumer source contract at an exact commit. Earlier pass results are useful evidence when available, not a merge gate. Check active ownership of the files this pass actually changes; stop only for a genuine collision or a missing required contract, and do not duplicate a completed pass. Use SKILLS-01 findings when available; do not duplicate an active Pipeline branch.

Workspace:
Use /home/ned/ai/depot only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/depot-worktrees and a new branch named docs/skills-02 (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

GitHub availability: use authenticated REST if GraphQL or a gh command is rate-limited. A missing Project item or unavailable Project API does not block repository edits, tests, commits, push or a PR. Use Git refs and available repository API evidence; mark unavailable coordination explicitly. If PR creation itself is unavailable, finish safe isolated work and push when Git transport works, then report PR creation pending rather than claiming completion. Do not treat the mere existence of an unrelated PR as a file collision.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Own affected canonical plugins/pipeline commands, skills and references. Inspect the existing single planning gate, approved scope, prompt generation, role dispatch, verification and terminal paths. Remove actual repeated or contradictory instructions and load detail only when its stage needs it.

Preserve requirements coverage, provider-neutral role intent, the separate driver/worker defaults, prototype authority, rendered checks, exact verification reuse, cleanup, every retained finding and one concise next action. Keep stage contracts and receipts; do not introduce another planner, orchestration engine, broker, schema or blanket review gate. Do not restructure code merely to reduce file size.

Acceptance and focused verification:
Walk one narrow docs repair, one ordinary Go/Templ task and one UI task through the existing workflow. Each has the required evidence and one applicable planning/review path. Report loaded bytes and removed duplication; do not claim token/time savings without measurement. Regenerate command aliases when canonical commands change and run affected workflow/role/context fixtures plus full composition.

Consumer canary:
Use one bounded Baseplate or Jig task to inspect the complete generated prompt/verification handoff; distinguish source-contract proof from an installed end-to-end run.

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
