# Pipeline Receipt: rail-exhaustion-ask-gate

- Date: 2026-08-08
- Branch: bionic/rail-exhaustion-ask-gate
- Base: policy/native-judgment-coding-rung -- **DEVIATION** from manifest `baseBranch: main` (see Deviations)
- Merge: APPROVE WITH FIXES (all findings resolved before emission); `noMergeOnCompletion: true`, not merged
- PR: https://github.com/Design-Machines-Studio/depot/pull/21 (stacked on #20)
- Chunks: 1 executed, 0 parallel
- Mode: full_cli
- Isolation: per-chunk-worktree
- Workflow class: feature
- Workflow class defaulted: false
- Decision profile: uncertainty low / consequence high (not defaulted)
- providerSplit: {claude: 3, codex: 0, openrouter: 4}
- eligibleProviderSplit: {codex: 0, openrouter: 4, targetProfile: codex-pro-20x, routingVariance: -65pp Codex}

## Deviations (receipted)

1. **Base branch.** Manifest declares `baseBranch: main`; this run branched from
   `policy/native-judgment-coding-rung` (PR #20). Verbatim reason: on plain
   `main` this run cannot execute at all. Both external coding rails were
   simultaneously unavailable on this macOS host -- the Codex subscription is
   capped until 12:54 local, and every automated OpenRouter rung fails closed in
   `cascade-dispatch.sh`'s `openrouter_allowed()` gate because
   `/usr/local/bin/workflow-authority` is not installed. PR #20 adds
   `native_judgment` as a last-resort coding rung strictly below both external
   rails, which is what makes any dispatch possible today. Verified before this
   run: a real (non-dry) `cascade-dispatch.sh --class config` returns exit 64
   with `{"dispatch":"native","model":"opus","fallback":true,"fallbackReason":"openrouter-unavailable-or-below-floor"}`.
   PR #21 rebases onto main once #20 lands.

2. **Provider variance.** Manifest `executor: codex` with `routingOverride`
   reasonCode `authoring-policy`. Implemented on the native rung (Opus) after a
   real `cascade-dispatch.sh --kind config --exhausted-rail codex` returned
   RC 64. Receipted as `requestedProvider: codex`, `attemptedProvider: claude`,
   `implementedBy: claude`, `fallback: true`,
   `fallbackReason: rail-exhausted-codex-capped-openrouter-broker-unavailable`.
   Target variance under `targets.enforcement.varianceReceiptRequired`.

3. **Security sign-off UNSATISFIED.** `routing-policy.json` declares
   `security-auditor-codex-signoff` as `required: true` on the Codex provider.
   Codex was capped, so **that lane did not run**. Per explicit user directive
   (2026-08-08, Trav), the Kimi K3 security lens satisfied the security review
   for this run. The Codex sign-off requirement is unsatisfied, not waived. No
   Codex sign-off happened.

4. **Fable used for review.** CLAUDE.md "Model & Effort Tuning" states "Never use
   Fable for implementation, code review, security, architecture". Fable ran the
   adversarial judgment lane per standing user directive #3, which overrides
   written policy. Policy file not rewritten to match.

5. **Kernel run id.** Caller supplied run id
   `rail-exhaustion-ask-gate-20260808`. The kernel derives `spec.run_id` from
   `manifest.feature` and resolves the lifecycle at
   `<lease_root>/runs/<spec.run_id>`, so bind-prediction could only ever address
   `.workflow-kernel/runs/rail-exhaustion-ask-gate`. That directory was
   initialized and used. The caller's pre-initialized directory is untouched and
   unused.

6. **Ordering.** Step 0d gitignore enforcement ran after branch creation rather
   than before, to avoid committing to the open PR #20 branch. All required
   entries were already present; no commit was needed.

## Evidence

See `plans/rail-exhaustion-ask-gate/final-requirements-crosscheck.md` -- 12 rows,
every one carrying a grep / build / test evidence type. No requirement
unaddressed.

## Review

- Lanes: GLM-5.2 (mechanical), Kimi K3 (security), Fable (adversarial), Kimi K3
  recheck, Kimi K3 final full-diff review.
- Iterations: 2 per-chunk + 1 final. Findings: 2 P1, 8 P2, 8 P3 -- **all fixed**.
- Deferred findings: none.
- Coverage gap: `security-auditor-codex-signoff` (Codex capped). Recorded, not
  waived.
- Cross-provider verification: implementation Claude-native, review OpenRouter
  (Kimi/GLM) -- genuinely different family.

## Cleanup

- Ephemeral removed: 0 (no baselines/screenshots produced -- config chunk, no UI)
- Feature-scoped retained: manifest, prompts, crosscheck, receipts, shadow
  artifacts, review artifacts
- Deferred findings: none
- Docker resources: none registered this run (no `plan-create`/`plan-compose`
  invoked); nothing to reconcile
- Reconciliation: complete -- no owned resources existed

## Branch & Worktree Inventory

### Created this run

| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| `.worktrees/pipeline/rail-exhaustion-ask-gate/01-exhaustion-ask-gate` | worktree | deleted | `git status --porcelain` empty, `git worktree remove` exit 0 |
| `pipeline/rail-exhaustion-ask-gate/01-exhaustion-ask-gate` | chunk-branch | deleted | `git merge-base --is-ancestor` true, `git branch -d` exit 0 |
| `bionic/rail-exhaustion-ask-gate` | feature-branch | kept -- no merge proof | never deleted by contract; PR #21 open against `policy/native-judgment-coding-rung` |

### Remaining after cleanup

| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| `bionic/rail-exhaustion-ask-gate` | feature-branch | not merged into main or origin/main; PR #21 open | `gh pr view 21` |

- Worktrees before: 1 (main tree only)   after: 1   pruned: 1
- Branches deleted: 1   blocked: 0
- `git status --porcelain`: clean

## Shadow

- Prediction sealed pre-`run.started` (13 predicted receipts), verification
  contract bound (`sha256:b518eb2b...`, revision 1) against the `not_declared`
  verification profile.
- Terminal comparison: **parity gap** -- `missing_authoritative_evidence`,
  difference `missing_receipt_transition`. Cause: the authoritative stream
  carries 21 receipts against 13 predicted; the prediction under-called the
  review-lane attempts (5 recorded, 0 predicted) and predicted
  `attempt_unmeasured` where the run produced real OpenRouter API usage.
  Observation-only; it did not gate, block, or convert any canonical result.
- Terminal artifacts retained (parity gap, not `match`), per the cleanup rule.
run-cost-summary: plans/rail-exhaustion-ask-gate/run-cost-summary.json (usage measured 4/6)
