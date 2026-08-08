# Pipeline Receipt: r1-review-burn-cuts

- Date: 2026-08-08
- Branch: bionic/r1-review-burn-cuts (HEAD ab6cef3)
- Base: policy/native-judgment-coding-rung  [DEVIATION -- manifest declares `main`]
- Merge: APPROVE WITH FIXES (noMergeOnCompletion: true -- PR only, no merge performed)
- Chunks: 5 of 6 executed and merged, 0 parallel; chunk 06 NOT STARTED (clean stop)
- Mode: full_cli
- Isolation: per-chunk-worktree
- Workflow class: feature (workflow_class_defaulted=false)
- decisionProfile: uncertainty medium / consequence high
- providerSplit: {claude: 0, codex: 5, openrouter: 0} implementation chunks
- eligibleProviderSplit: {codex: 5, openrouter: 0, targetProfile: codex-pro-20x (65/0/35),
  routingVariance: +35pp toward Codex}
  Cause: all six chunks carry a manifest `routingOverride` with reasonCode `authoring-policy`
  and splitAttempted:true. Every chunk is coverage- or routing-policy authoring. None is an
  eligible flexible-bucket chunk, so all five are `routingExclusions`, and the 65/0/35 target
  has an empty denominator this run. The variance is explained, not silent.

## Chunks

| Chunk | Status | Review | Findings | Merged | Pushed |
|---|---|---|---|---|---|
| 01-selective-loop-rerun | complete | focused Codex, 2 passes | 4 P1 + 3 P2, 6 fixed, 1 carried to 03 | yes | yes |
| 02-review-tier-enforcement | complete | focused Codex, 3 passes (extended) | 1 P1 + 3 P2, all fixed | yes | yes |
| 03-lane-diff-scoping | complete | focused Codex, 2 passes | 3 P1 + 1 P2, all fixed, closed 01's carry | yes | yes |
| 04-browser-trio-slimming | complete | focused Codex, 3 passes (extended) | 11 P1, all fixed | yes | yes |
| 05-model-matrix-enforcement | complete | focused Codex, 2 passes | 3 P1 + 2 P2, 4 fixed, 1 rejected | yes | yes |
| 06-routing-invariants-operator-profiles | NOT STARTED | -- | -- | no | no |

## Final review

- Codex full-diff `security-auditor-codex-signoff`: BLOCKED, then PASS after fix ab6cef3.
  Blocking P1: only the Codex security lane was forced to re-run on iteration 2+, so the
  independent OpenRouter security lens could be skipped exactly as the loop converged.
- Kimi K3 independent lens (`moonshotai/kimi-k3` via openrouter-wrapper.sh): DEAD LANE, empty
  output on the corrected stdin invocation. Not relaunched, per the dead-lane rule.
- `./tools/validate-composition.sh --all`: PASS (includes the 1106-test kernel suite).

## Loop extensions (receipted, per zero-deferral)

- Chunk 02 extended 2 -> 3 passes rather than defer 1 P2: the tier-policy validator anchor still
  passed when a weakening exception paragraph was appended.
- Chunk 04 extended 2 -> 3 passes rather than defer 4 P1s: a second independent parity sample
  found four more checks that had lost thresholds or severities.

## Rejected finding (with reasoning, not deferred)

- Chunk 05 review asked to remove `native_judgment` from both coding ladders in
  `model-cascade.json`. REJECTED: that file is not in chunk 05's diff, and base commit 63101e8
  added the rung deliberately as a last-resort. Removing it would silently revert PR #20.

## NOT-COVERED

- R0 baseline: `plans/r0-measurement-backbone/run-cost-summary.json` is absent from this clone
  and `docs/cost-baselines/` holds only the adaptive-fusion baseline. The chunk 01 Step 0 copy
  was skipped. No substitute was fabricated. The other run-cost-summary.json files present
  belong to sibling runs and are not R0.
- Chunk 06 (routing invariants, operator profiles, family-independent second opinion) not started.
- Kimi K3 final-review lane returned empty; its compound-coverage-loss analysis is missing.
- Browser verification: not applicable, no UI chunks.
- Kernel shadow prediction/observation/comparison: shadow unavailable, see below.

## Kernel

- Fresh run initialized at `.workflow-kernel/runs/r1-review-burn-cuts`. The stale prior-run state
  directory was moved aside to `r1-review-burn-cuts.tombstone-20260808T105915Z`, not appended to.
- Verification contract bound, revision 1,
  digest sha256:5e696da32a9a6dd8d18a2a3a353deb942467bb949a5a72689bb8c88f8a7dc7ca.
- `record-attempt` called once per chunk: 5 lanes, 10 receipts.
- `emit-cost-summary`: `run-cost-summary: plans/r1-review-burn-cuts/run4/run-cost-summary.json
  (usage measured 5/5)`.
- SHADOW UNAVAILABLE. Reason: authoring a fresh independent prediction was judged unaffordable
  against the orchestrator's own Claude session budget, which had already killed two prior
  attempts of this manifest. The prior sealed prediction was deliberately NOT reused. Shadow is
  observation-only and never gates the canonical result; the canonical result stands unchanged.

## Measured cost

- Codex (gpt-5.6-sol), all implementation and review: 2,669,403 tokens across 20 exec sessions.
- OpenRouter: 1 attempted lane (Kimi K3), returned empty, no usage recorded.
- Claude: orchestration only. Zero coding, zero code review.
- Kernel-measured lanes: 5/5, 180,119 input bytes, 14,220 s wall.

## Review input-bytes delta (the point of the feature)

Browser trio agent definitions, measured:

| Definition | Before | After |
|---|---:|---:|
| ux-quality-reviewer.md | 27,969 | 11,769 |
| visual-browser-tester.md | 22,622 | 10,038 |
| ui-standards-reviewer.md | 17,337 | 9,644 |
| **Total** | **67,928** | **31,451** |

-36,477 bytes, -53.7%, on every run that dispatches the browser trio. Parity verified by two
independent samples after the first parity claim proved false.

The other three mechanisms (selective lane re-run, per-lane diff scoping, review-tier
enforcement) reduce per-iteration input by construction, but their delta is run-shaped and was
NOT measured this run -- the R0 instrument that would grade them is the missing baseline above.

## Branch & Worktree Inventory

### Created this run

| Ref | Kind | Disposition | Proof |
|---|---|---|---|
| .worktrees/pipeline/r1-review-burn-cuts/01-selective-loop-rerun | worktree | deleted | removed clean |
| pipeline/r1-review-burn-cuts/01-selective-loop-rerun | chunk-branch | deleted | merged, `git branch -d` |
| .worktrees/pipeline/r1-review-burn-cuts/02-review-tier-enforcement | worktree | deleted | removed clean |
| pipeline/r1-review-burn-cuts/02-review-tier-enforcement | chunk-branch | deleted | merged, `git branch -d` |
| .worktrees/pipeline/r1-review-burn-cuts/03-lane-diff-scoping | worktree | deleted | removed clean |
| pipeline/r1-review-burn-cuts/03-lane-diff-scoping | chunk-branch | deleted | merged, `git branch -d` |
| .worktrees/pipeline/r1-review-burn-cuts/04-browser-trio-slimming | worktree | deleted | removed clean |
| pipeline/r1-review-burn-cuts/04-browser-trio-slimming | chunk-branch | deleted | merged then amended, `git branch -D` |
| .worktrees/pipeline/r1-review-burn-cuts/05-model-matrix-enforcement | worktree | deleted | removed clean |
| pipeline/r1-review-burn-cuts/05-model-matrix-enforcement | chunk-branch | deleted | merged, `git branch -d` |
| bionic/r1-review-burn-cuts | feature-branch | KEPT | no merge proof into main; never deleted |

### Remaining after cleanup

| Ref | Kind | Reason kept | Follow-up |
|---|---|---|---|
| bionic/r1-review-burn-cuts | feature-branch | PR open, unmerged | merge the PR |

- Worktrees before: 1  after: 1  pruned: 0 (all 5 chunk worktrees created and removed)
- Branches deleted: 5   blocked: 0
- `git status --porcelain`: clean

## Incidents

1. The orchestrator's own 10-minute foreground command cap killed the chunk 04 fix pass
   mid-verification. Work was salvaged from the worktree, not relaunched against the same
   failure mode. Subsequent dispatches ran detached.
2. A dispatcher mode-routing bug prepended the commit-protocol preamble to a `recheck` dispatch,
   and that agent committed instead of reviewing. Corrected, and a genuine read-only recheck was
   run -- which then found four more dropped P1 checks in chunk 04.
3. Backgrounding a `validate-composition.sh --all` subshell together with a dispatch silently
   killed the job. Validators were subsequently run in the foreground, separately.
