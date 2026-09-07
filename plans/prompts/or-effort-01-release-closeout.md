# OR-EFFORT-01 — PR #127 release closeout

> COMPLETED 2026-09-07: PR #127 is merged, tagged, synchronized and proven by
> an installed consumer call. Historical prompt; do not rerun.
> Next: [UI-READY-03](ui-ready-03-repository-target-discovery.md).

Prepared 2026-09-07. Human recommendation: GPT-5.6 Sol, Codex subscription,
high effort; exactly one fallback GPT-5.6 Terra, Codex subscription, high.
The installed router reports both attemptable. Matrix evidence: 2026-08-27.
Cost: included subscription; installed OpenRouter canary at most $0.25.

Pasting the following prompt into an execution session explicitly authorizes
the listed merge, release and cache actions after its checks. This planning
session has performed none of those actions.

```text
Complete OR-EFFORT-01 by closing out Depot PR #127 and proving the installed fix.

Repository: /home/ned/ai/depot
GitHub: Design-Machines-Studio/depot
PR: https://github.com/Design-Machines-Studio/depot/pull/127
Prepared main/base: 76267e0e10845e1f9ea4a5eb533b6ca9628b12be
Prepared PR head: 0332eac31fb35e3d91b6ddffb056604f49716fd2
Existing branch: fix/openrouter-effort-contract
Existing worktree: /home/ned/ai/depot-worktrees/openrouter-effort-contract
Owning plugins: model-router 0.6.2 and openrouter 1.20.2
executorRole: builder-deep
executorCapabilities: [read-repository, write-repository, tool-use, long-context, structured-output]
executorEffort: high

Authorization for this execution:
After the checks below succeed, merge PR #127, publish model-router-v0.6.2 and
openrouter-v1.20.2 using Depot's existing release process, synchronize these
plugins in Claude and Codex, and run the bounded paid consumer canary. This is
authorization for this specific release, not unrelated merges, versions, remote
branch deletion, workspace cleanup or account-budget changes.

Read AGENTS.md, its direct instruction references, CLAUDE.md and current release,
cache-sync and model-router/OpenRouter contracts. Preserve the dirty primary
checkout and all other worktrees. Refresh authenticated PR/main state, checks,
reviews, tags and the existing worktree's HEAD/status. If the head moved, inspect
the intervening diff and verify the current result. Do not overwrite concurrent
work. Reuse the existing clean implementation branch for necessary repairs; do
not create a duplicate implementation. Use an isolated current-main worktree for
trusted-main release checks.

Already delivered in source:
The dispatcher carries normalized effort through OpenRouter read and bounded-write
paths as reasoning.effort. Receipts distinguish requested, normalized and
transmitted settings; omitted direct effort stays default-unknown, and historical
receipts do not gain invented transmission evidence. Only the router's OpenRouter
dependency/runtime floor moves to >=1.20.2. Canonical versions, generated manifests
and dependency graph are synchronized.

Inspect the final change once for concrete defects within that scope. Confirm
the actual outgoing request and returned report agree, old direct invocations
remain compatible, fallback remains bounded, and unavailable effort does not
become a pass. Treat a transmitted setting as request evidence, not a measurement
of the model's internal reasoning. Fix every retained P1/P2/P3 finding before
merge. Do not manufacture findings or repeat broad review after convergence.

Relevant surfaces are the model-router dispatcher, bounded-write adapter, bundle
floors, receipt contract and terminal renderer; the OpenRouter wrapper and
invocation protocol; their existing tests and canonical manifests.

Verification evidence at prepared head:
- Coordinator reran the real loopback read/write effort regression: all four
  normalized values passed on both paths.
- Coordinator reran tools/test-terminal-model-report.sh: 37 assertions passed.
- PR reports test-model-router.sh: 134 assertions; test-openrouter-runner-policy.sh:
  41 tests; resolution validation and full composition passed.
- Hosted check is Codesmith SKIPPED; no submitted review or required hosted
  composition gate was present. Inspect current settings; do not report absent
  or skipped hosted checks as green CI.

Reuse exact-head verification when its provenance is adequate. Establish full
./tools/validate-composition.sh --all success at the final merge candidate and
perform the repository's release preflight. If repairs change the implementation,
rerun affected tests and required composition validation, commit and push the
repairs, and recheck the exact PR head before merging. Do not add unrelated CI.

Merge using the repository's existing merge policy, bound to the verified PR head.
Record the resulting trusted-main SHA and inspect the actual merged tree. Run
the required trusted-main verification before publishing. If main moved, inspect
the change instead of assuming PR-head evidence covers the merged result.

Publish only model-router 0.6.2 and openrouter 1.20.2. Verify tag names and target
commits before pushing. Never move or overwrite an existing tag; if already
published correctly, verify and reuse it. An incompatible existing tag is a
concrete blocker, not permission to invent another version.

Canonical Claude manifests remain authoritative. Do not hand-edit Codex manifests
or command aliases. If a repair changes canonical commands or indexed content,
regenerate the applicable surfaces and search index. Evaluate dependency floors;
do not bump unrelated plugins with unchanged compatible calls.

Synchronize both changed plugins into Claude and Codex through existing tools.
Verify selected versions, content identity and coherent bundle resolution for
each harness. Preserve unrelated installed versions/configuration and any active
session bindings. Do not fabricate an unavailable parent subscription from a
nested probe's uncertainty.

Run one bounded real consumer analysis from an exact Assembly consumer revision
through the installed router/OpenRouter path. Use current approved routing and
capability evidence; do not falsify subscription availability or edit global
routing to force a canary. A native-only result does not prove OpenRouter. If the
live route cannot exercise the changed transport, report that specific proof gap
and the smallest next action; do not mislabel offline or direct-wrapper-only
evidence as a complete routed consumer pass.

Check available OpenRouter credits and any configured limit. Keep the canary's
paid cost below $0.25 and respect the developer's $50/month maximum. Do not add
credits, raise limits or launch a benchmark campaign. Record attempted/served
participant, effort sent, provider usage/cost, duration and outcome. Do not place
concrete identities in worker prompts.

Non-goals: no model portfolio rollout, new budget system, browser-discovery fix,
instruction rewrite, Pi/Floor implementation, new service, broker or schema family.
The following code chunk remains UI-READY-03 after this delivery is complete.

GitHub terminal state:
PR #127 merged after required verification, with a concise release/consumer-proof
update. No native Issue creation/closure/reassignment. Use only Project 1, Assembly
Coordination, whose current item is Review/P1/Tooling. Mark Done only when this
release and its consumer proof are complete; otherwise explain the real remaining
gap and use the appropriate existing status. No new Project.

At about 40 tool calls, stop broad exploration but finish focused repairs,
verification, commits, pushes, authorized publication and honest closeout.

Final response: strongest achieved delivery level, exact PR/merge/tag/cache
identities, canary result and one next action. Include SIMPLICITY-CHECK,
NOT-COVERED and COMMANDS-RUN. Emit one compact terminal model-and-cost report:
role, attempted/served participant, rail, requested/transmitted effort, duration,
outcome, measured tokens, measured paid cost, subscription calls, fallbacks and
unavailable measurements. Never infer subscription charges from API equivalents.
```
