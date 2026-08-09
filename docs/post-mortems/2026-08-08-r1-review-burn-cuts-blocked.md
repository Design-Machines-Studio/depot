# Run Post-Mortem: r1-review-burn-cuts

Date: 2026-08-08
Outcome: BLOCKED at chunk 01 dispatch. 0 of 5 chunks implemented.
Workflow class: feature (`workflow_class_defaulted: false`)
Decision profile: medium/high (`decision_profile_defaulted: false`)

## providerSplit (measured)

| Provider | Chunks | Tokens | Cost |
|----------|--------|--------|------|
| codex | 0 | 0 | $0.00 |
| openrouter | 0 | 0 | $0.00 |
| claude | 0 coding | orchestration only | not separately metered |

Zero tokens were billed on either coding rail. Codex refused at the account
usage limit before any turn produced output; the OpenRouter adapter exits
fail-closed before provider contact. `run-cost-summary.json` carries
`lanes: []` and `measurement_coverage.usage.missing: 1` -- honest absence, not
missing instrumentation.

## eligibleProviderSplit

All 5 chunks are `kind: config` and would normally be OpenRouter-eligible under
`deficit-round-robin`. All 5 carry an explicit
`routingOverride.reasonCode: authoring-policy` pinning them to Codex, sourced
from the parked Phase 1 postmortem finding that routing authoring-policy work to
the cheapest model misclassified it. Those overrides were honoured; no chunk was
re-routed to a cheap mechanical model.

`routingExclusions`: all 5 chunks, reason `provider-outage-or-cap` -- neither
rail was reachable.

`routingVariance`: not measurable. Zero eligible dispatches completed, so the
target denominator is zero.

## Misroutes

None. No Claude task was classified `misrouted`. Critically, no
`executor: codex` chunk was inline-implemented on Claude. The contract's hard
rule held under pressure: a 13-hour cap is exactly the condition under which an
orchestrator is tempted to "just do it itself", and that is the documented
misroute this rule exists to prevent.

## Quality ledger

- Issues found by provider: none -- no review gate was reached.
- Regressions shipped by cheaper models: none -- nothing shipped.
- Retries: 1 dispatch attempt, 1 cascade consultation (twice, with and without
  `--exhausted-rail codex`, to rule out flag-handling as the cause of RC 76).
- Cap descents: 1, terminal.

## Kernel reliability

- Shadow: available and exercised end to end. `bind-prediction` sealed 34
  predicted receipts pre-`run.started`; `observe-pipeline` consumed 10
  authoritative receipts; `compare` returned
  `unexpected_authoritative_transition` / `extra_receipt_transition`,
  `semantic_match: false`, `safe_to_promote: false`. Correct behaviour: the
  prediction forecast a clean run, the authority recorded a dispatch failure.
- Browser recovery: not applicable. Zero UI/Integration chunks, so the MCP
  pre-flight correctly recorded `not required`.
- Docker: zero owned resources created; reconciliation not applicable.
- Repository verification planner: `unavailable` (no `.dm/verification.json`).
  Compatibility path used the repository-native validator suite.

## Findings worth carrying forward

### F1 (P2) -- Manifest template omits `executionMode`, which hard-blocks `bind-prediction`

`translate_manifest` defaults `executionMode` to `generic` when the key is
absent. Any receipt claiming the truthfully detected `full_cli` then fails
`_require_spec_receipt_context` with an opaque digested `unsafe_payload` error.
Resolved this run by writing the host-detected value into the manifest before
`run.started`. Proposal: promptcraft should emit `executionMode` in the manifest
template, or `pipeline-run` should write it during host pre-flight before the
first kernel call. AWAITING APPROVAL.

### F2 (P2) -- Kernel CLI errors are digest-redacted, making misuse near-undiagnosable

Every input error surfaces as
`{"code":"unsafe_payload","details":{"exception_type":"value-sha256:..."}}`.
Four distinct failures this run (receipt context mismatch, regression lacking
executable verification, wrong initial-binding `reason_code` and obligation set,
missing `schema_version` on a contract receipt) all produced the byte-identical
error string. Each required dropping to a direct `python3.12` traceback to
diagnose. That is roughly a dozen tool calls spent on error archaeology.
Redaction is correct for durable receipts; it is counterproductive on
interactive stderr. Proposal: emit a stable non-secret `reason_code` enum
(`contract_regression_unproven`, `run_spec_receipt_context_mismatch`,
`initial_binding_justification_invalid`, ...) alongside the digest.
AWAITING APPROVAL.

### F3 (P1 for reliability, not for correctness) -- Single-rail dependency

With OpenRouter automated dispatch fail-closed pending the broker, Codex is the
ONLY implementation rail. One account-level cap therefore takes the entire
pipeline to zero. This is the direct, measured cost of the broker gap and is the
strongest available argument for prioritising the Workflow Authority Broker.
No code change proposed here; this is evidence for R3 sequencing.

### F4 (P3) -- `plans/` is gitignored but partly force-added

`rm -rf <worktree>/plans` deleted ~80 tracked files. The repo-cleanup contract's
dirty-worktree guard caught it and blocked removal, and it was fully repaired.
Proposal: orchestrator guidance should stage read-only chunk inputs outside the
worktree, or remove only the exact file it added. AWAITING APPROVAL.

### F5 (P3) -- `rtk` mangles `git log` SHAs

`git log --oneline -3 main` returned a commit that was not main's tip, while
`git show-ref` and `rtk proxy git rev-parse` agreed on the true SHA. Any
orchestrator step that trusts filtered `git log` output for identity is unsafe.
This run used `rtk proxy git` for all load-bearing git reads. Proposal: document
the `rtk proxy` requirement for identity-critical git reads. AWAITING APPROVAL.

### F6 (P3) -- `validate-workflow-kernel.py` needs python3.12 explicitly

Bare `python3` on this machine is 3.9 and fails at check 01 with
`TypeError: dataclass() got an unexpected keyword argument 'slots'`, which reads
as a repository defect. Proposal: give the validator the same interpreter probe
the kernel launcher already has, or fail with a clear version message.
AWAITING APPROVAL.

## Recommendations, ranked

1. F3 -- prioritise the Workflow Authority Broker. Expected effect: removes the
   single point of failure that made this run's yield zero. Confidence: high.
   Evidence: this run.
2. F2 -- add a stable reason_code to kernel CLI errors. Expected effect: saves
   roughly ten tool calls per kernel-integrating run. Confidence: high.
3. F1 -- emit `executionMode` in the manifest template. Expected effect: removes
   a hard blocker at the first kernel call. Confidence: high.
4. F6, F5, F4 -- diagnosability and safety papercuts. Confidence: medium.

All recommendations are proposals only. No plugin source or routing policy was
edited from this post-mortem.

## Recurrence check (performed)

`docs/pipeline-metrics/ledger.md` shows the single-rail / broker-gap pattern in
four consecutive entries:

- 2026-07-15 `ai-developer-workflow-kernel` -- codex unavailable, openrouter 0
- 2026-07-22 `adaptive-fusion-verification` -- outage:3, openrouter 0/no execution
- 2026-08-07 `r0-measurement-backbone` -- codex cap + `host_authority_unavailable`;
  top recommendation was already "Wire the Workflow Authority Broker"
- 2026-08-08 `r1-review-burn-cuts` (this run) -- identical, and the first to
  yield literally zero chunks

That is 4 occurrences against a promotion threshold of 3. **F3 is promoted to a
Standing Recommendation.** The broker is no longer a nice-to-have sequencing
preference; it is the measured cause of a total-loss run.
