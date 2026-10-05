# AUTO-REVIEW-01 candidate evidence

Supported direct tasks continue from a verified pushed PR into dm-review's
proportional review-and-repair path. Pipeline uses its existing final gate.
The canonical contract is
[automatic implementation closeout](../plugins/dm-review/skills/review/references/automatic-implementation-closeout.md).
No event trigger covers arbitrary GitHub PR creation outside these sessions.

## Source trace

- Direct: Assembly Coordinator prompt guidance and promptcraft template →
  canonical contract → `review-next-action.sh` → one loop or the existing
  remaining-evidence path → repair delivery → validated closeout.
- Pipeline: execution orchestrator/Codex adapter → integrated PR push → existing
  Step 4 mode/roster → repair push → affected checks/lanes → single owner closeout.
  The contradictory early loop that repeated full review was removed.
- UI/UX: selected design lanes and front-facing repair drafts → `design-consultant`
  → model-router's required native participant. Backend, accessibility, security
  and functional roles retain their existing policy.

## Candidate proof and limits

`tests/test_auto_review_candidate.py` exercises direct-loop and Pipeline owner
mechanics in isolated repositories with local bare remotes. Both repair, commit,
push, verify the remote head, reject stale-head evidence, preserve fresh validated
closeout evidence, reuse unchanged evidence, and preserve foreign checkout data.
These are fixture paths, not autonomous model execution of a generated consumer
prompt or a full installed Pipeline campaign. The source task also exercises
candidate direct closeout on [PR #163](https://github.com/Design-Machines-Studio/depot/pull/163):
automatic quick review after push, one retained P2 for the runtime router version
floor, repair/push, and affected-lane recheck. Final validated receipts are linked
from the PR; this source session remains distinct from installed consumer proof.

`tools/test-review-next-action.sh` covers quick/full, sensitive, rendered-only,
retained findings, unchanged reviewed heads and dirty boundaries.
`tools/test-model-router.sh` adds required design selection, exact served identity,
substitution rejection and unavailable/no-fallback cases; other transport and
availability regressions remain in that suite. Existing Kernel closeout tests
cover invalid/missing receipts, sealed recovery and evidence retention.

A bounded live design dispatch on 2026-10-05 requested and served
`claude-opus-5-5` through native `claude-cli`, medium effort, in 8 seconds.
Its public companion records `evidenceSource: live`, `transportStub: false`,
`disposition: completed`, and no fallback. This proves native identity/transport
for one bounded text task, not UI browser acceptance. Auth was subscription;
allowance telemetry and billed cost were unavailable. Provider tokens: 2 input,
34,521 cache creation, 0 cache read, 248 output (154 thinking included).
The real private receipt and output are retained in the task-owned proof root.

The identity is supported by Anthropic's [model overview](https://platform.claude.com/docs/en/models/opus-5-5/overview)
and [Claude Code configuration](https://support.claude.com/en/articles/11940350-claude-code-model-configuration),
checked 2026-10-05. PR #151 at `ce431c5b924ffd9e7fbc4498c2caefe710ded4af`
changes only `docs/sol61-benchmark-evidence-2026-09-30.md`; its proposed Claude
options are neither merged policy nor live-model proof. This candidate does not
modify that PR or its document.

## Release/install boundary

Changed plugins: dm-review 1.85.0, Pipeline 1.71.0, project-manager 1.19.0,
model-router 0.11.0. Kernel runtime and project-scaffolder hooks are unchanged.
New dependency floors bind callers to the new closeout/design contract.

After human review/merge: verify trusted main; tag the four affected plugins;
synchronize Claude and Codex through the normal cache procedure; restart/reload
sessions; run one normal installed direct task and one installed Pipeline canary,
including applicable design and browser cases. Source fixtures and this live
router probe do not establish installed-session automation. No merge, tag,
publication or installed-cache mutation is part of this PR.

## SIMPLICITY-CHECK

One dm-review contract, short caller references, existing owner/state and
closeout mechanics; one existing design role with a single required candidate.
No registry, webhook, daemon, scheduler or fleet hook rollout.

## NOT-COVERED

Installed consumer prompt/Pipeline canaries, rendered UI acceptance, real external
blocker Issue creation, account-wide monthly budget enforcement, and arbitrary
out-of-workflow PR events. Existing Issue search/reuse policy remains mandatory;
no external dependency was discovered in this source change.

## Playwright review transport follow-up

Formal dm-review and Pipeline review/parity browser checks now require host
Playwright. T3 remains available for operator design handoff and verified target
context; missing T3 tabs or phone automation never gate Playwright startup.
The existing MCP/repository-harness and engine recovery paths remain bounded.
No new browser stack or development target is installed.

Readiness inputs and reusable browser packets use version 2 with required
`automationTransport: "playwright"`. T3, unknown and legacy packets are rejected
rather than relabeled; actual Playwright recapture is required. Typed fixtures
cover both readiness rejection and packet creation/reuse rejection, retaining
source/head/case/artifact validation and cleanup protections.

A live isolated Firefox Playwright MCP canary opened `about:blank`, captured an
accessibility snapshot, clicked a snapshot-provided button and observed its live
status change, while T3 reported no attached preview. A screenshot initially hit the MCP output-root restriction; a unique filename
succeeded. Its exact returned source-checkout copy was retained, byte-verified
and removed immediately. This proves the host transport, interaction and
artifact path; it is not consumer application or persona proof.

Depot Issue #162 is a separately owned Kernel package-selector repair at
`fix/162-deleted-go-packages`. This change does not modify its checkout or Kernel
runtime; normal integration of its manifest change remains a release step.
