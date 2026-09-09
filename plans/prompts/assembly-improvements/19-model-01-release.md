# MODEL-01-RELEASE — Publish the merged routing versions and verify installations

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
Implement only MODEL-01-RELEASE: Publish the merged routing versions and verify installations.

Repository: Design-Machines-Studio/depot
Checkout for discovery: /home/ned/ai/depot
Prepared exact base (2026-09-08): 386b98e26f493cc220047c981cd5c01b1513b24d
Owning plugin: none; repository-owned instructions/workflow
executorRole: builder-deep
executorCapabilities: ["read-repository", "write-repository", "structured-output", "tool-use"]
executorEffort: low

Prerequisite and collision boundary:
Optional publication session: paste this prompt only when authorizing the exact publication/cache operations below. It is not required to begin INSTRUCTIONS-01. Complete RELEASE-01 first if the same comparator defect still blocks honest preflight.

Workspace:
Use /home/ned/ai/depot only to inspect Git metadata and fetch origin/main. Record the current exact SHA. If it has advanced from the prepared base, inspect the relevant delta and continue from refreshed main when the same scope remains valid; never revert newer work to the snapshot. Create a clean worktree at an unused path under /home/ned/ai/depot-worktrees and a new branch named docs/model-01-release (use fix/ for executable changes). Choose a unique suffix if that branch/path already has an owner. Preserve the primary checkout and all existing worktrees: no stash, reset, clean, rebase, branch switch, removal or discarded files. Recheck open PRs and file ownership before writing; do not duplicate active work.

GitHub availability: use authenticated REST if GraphQL or a gh command is rate-limited. A missing Project item or unavailable Project API does not block repository edits, tests, commits, push or a PR. Use Git refs and available repository API evidence; mark unavailable coordination explicitly. If PR creation itself is unavailable, finish safe isolated work and push when Git transport works, then report PR creation pending rather than claiming completion. Do not treat the mere existence of an unrelated PR as a file collision.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Explicit publication scope: model-router 0.7.0, pipeline 1.67.0 and project-manager 1.14.0 from the merged PR #131 lineage. Verify exact source/PR history, trusted-main tests, current manifest versions, all retained review findings and release tags before any publication. If these target versions have been superseded, stop with the actual versions for a revised complete prompt; do not publish arbitrary later changes. Preserve PR #130's OpenRouter 1.20.3 source and do not tag unrelated plugins.

Inspect existing tags first: validate an already correct immutable tag and skip creating it; never move or replace a published tag. Run the documented release preflight and resolve only authorized target prerequisites. After trustworthy checks pass, create/push only the missing exact annotated target tags and synchronize the intended Claude and Codex installations using repository-supported plugin commands. Do not hand-edit generated files or caches, change credentials/accounts, or remove historical worktrees. A real unresolved preflight/review failure blocks publication.

Verify each installed plugin tree against its tagged source, resolve coherent per-harness bundles, and run one bounded real consumer canary. Report source, trusted-main, publication, cache and consumer evidence separately. No new application feature or unrelated plugin release.

Acceptance and focused verification:
Exact target tags and installed versions match verified source in both harnesses; current role recommendations use the intended policy; a real bounded consumer canary succeeds without fabricated test or model claims. Required unavailable CI/review lanes remain explicit. Keep paid canary spend within the common cap. Record exact commit/tag objects and model/cost evidence.

Consumer canary:
Use a current Baseplate or Jig repository at an exact commit for a bounded analysis of its declared verification authority, or an equally small approved development task. State precisely whether tests ran. Verify installed behavior, not merely a source-checkout fixture.

Working constraints:
Build for two trusted developers and self-installed, federated co-op intranets of 5–50 people with trusted internal Fixtures. Apply YAGNI, pragmatic DRY, Live Wires/component reuse, accessibility, performance and maintainability. Preserve real authorization, credential, data-loss and release protections. No enterprise infrastructure. The driver retains design/integration/final acceptance; workers get bounded ownership. Route only role/capabilities/effort, with no concrete identities in participant packets or automatic inheritance of driver/max effort.

Use a direct, proportionate workflow and reuse still-exact evidence. No automatic full Pipeline/adversarial suite for instruction edits. Fix every retained P1/P2/P3 and verify affected behavior; stop review churn after convergence. Routine implementation choices are yours; ask only for a real missing decision or authorization.

Economics:
Refresh installed routing/matrix evidence before dispatch. Prefer eligible subscriptions and useful bounded OpenRouter offload. Paid calls have a $0.25 total ceiling, subject to known remaining monthly budget; $50/month is a goal, not verified headroom. Use deterministic checks where sufficient. Respect real export restrictions; report unavailable lanes and distinguish fixtures from actual calls.

Publication and terminal state:
The explicit tag/cache operations in this prompt are authorized only when the user chooses to run this publication session. Do not merge a PR. Reuse existing authoritative release/cache documentation, verify all exact target tags and both installed trees, and report the strongest delivery level reached. Do not change unrelated plugins or add an application release. If repository repairs are needed beyond this publication scope, return the exact blocker for a separate bounded repair. No empty commit or PR is required for tag/install operations; update existing release evidence only within this explicit scope. Project 1 may reach Done only for the exact represented delivered outcome.

Treat 40 tool calls as an exploration checkpoint; finish authorized repairs, verification, commit, push and PR creation. Keep updates brief.

Final report:
Report result, exact base/head, changes, actual checks, PR/Project state, delivery level and one next action. For routed work, report role, attempted/served participant, rail, effort, duration, outcome, measured tokens/cost, subscription calls, fallbacks and unavailable measurements. Finish with SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
```
