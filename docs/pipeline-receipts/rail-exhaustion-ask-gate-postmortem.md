# Run Post-Mortem: rail-exhaustion-ask-gate

Date: 2026-08-08
Branch: bionic/rail-exhaustion-ask-gate (PR #21, stacked on #20)
Workflow class: feature
Decision profile: uncertainty low / consequence high

## providerSplit (measured)

| Provider | Lanes | Tokens | Cost | Source |
|---|---|---|---|---|
| claude (native rung + Fable) | 3 | 52,014 usage_count on the implementation lane; input_bytes 37,337 | $0 billed (subscription) | `estimated_input_bytes` for the chunk; `attempt_unmeasured` for the Fable lane |
| codex | 0 | 0 | $0 | account-capped until 12:54 local; zero calls attempted after the first cap probe |
| openrouter | 4 (3 measured + 1 failed) | 51,014 combined prompt+completion across 3 measured lanes | $0.3706011 | `openrouter_api_receipt` x3 |

OpenRouter measured detail:

| Lane | Model | Serving provider | Prompt | Completion | Cost |
|---|---|---|---|---|---|
| review-mechanical | z-ai/glm-5.2 | Friendli | 5,910 | 12,923 | $0.0651352 |
| review-security | moonshotai/kimi-k3 | DigitalOcean | 5,959 | 8,587 | $0.1393479 |
| review-security-recheck (attempt 1) | moonshotai/kimi-k3 | -- | -- | -- | failed: stream ended without [DONE]; recorded, not hidden |
| review-security-recheck (attempt 2) | moonshotai/kimi-k3 | DigitalOcean | 8,722 | 9,913 | $0.16611795 |

`run-cost-summary.json`: 6 lanes, usage measured 4/6, cost measured 3/6.

## eligibleProviderSplit and variance

- Eligible flexible chunks: 1 (`01-exhaustion-ask-gate`, kind `config`).
- Target profile: codex-pro-20x, 65 Codex / 0 Claude / 35 OpenRouter.
- Actual eligible: codex 0%, openrouter 0%, claude-native 100%.
- Variance: **-65pp Codex, -35pp OpenRouter**, fully explained below.

### routingExclusions

| Chunk / lane | Reason |
|---|---|
| `01-exhaustion-ask-gate` | Codex account-capped (outage); automated OpenRouter fail-closed at the missing `/usr/local/bin/workflow-authority` broker. Cascade RC 64 selected the native rung. |
| `security-auditor-codex-signoff` | Codex capped. Lane did not run. Recorded as a coverage gap, not waived. |

## Misroutes

**None.** The chunk carried `executor: codex`; the orchestrator did not implement
it inline on its own authority. It ran the real `cascade-dispatch.sh` with
`--exhausted-rail codex`, received RC 64 (`{"dispatch":"native","model":"opus",
"role":"native_judgment","fallback":true}`), and re-dispatched in-process
through the native path exactly as the RC 64 row directs. Provider evidence is
complete and honest on every receipt: `requestedProvider: codex`,
`attemptedProvider: claude`, `implementedBy: claude`, `fallback: true`.

This is a **target variance requiring a receipt** under
`targets.enforcement.varianceReceiptRequired`, not a misroute. It is receipted
here, in `receipt.md`, and in PR #21's body.

## Quality ledger

| Finder | Severity | Finding | Outcome |
|---|---|---|---|
| Fable (adversarial) | P1 | Ask satisfiable by an agent answering itself; `authorized_by` a self-attested constant; orchestrator lacks `AskUserQuestion` and is a subagent | Fixed: operator defined, non-operators excluded, `ask_evidence_ref` required, delegated handoff specified |
| Kimi K3 (security) | P1 | Same self-authorization gap, independently found | Fixed (same change) |
| Fable | P1 | `claude_native` offered while `implementedBy` enum is `{codex\|openrouter}` -- forces a false `codex` label, i.e. the relabeling the step forbids | Fixed: narrow stated enum exception at all three sites |
| GLM-5.2 | P2 | Kill switch evaluated after the ask; a sequential reader could dispatch first | Fixed: step 0 fails closed before any pause |
| Kimi K3 | P2 | No fail-closed behavior on missing/malformed policy | Fixed |
| Kimi K3 + Fable | P2 | dm-review gap-and-continue silently cancels the pipeline's never-waive-final-review rule | Fixed: options (b) and (c) both unavailable for the pipeline final review |
| Fable | P2 | Authorization survives same-run-id resume and post-reset retries | Fixed: consumed per attempt, void on headroom return, void on any resume |
| Fable | P2 | One ask could pre-authorize the whole run | Fixed: `chunks` restricted to ids that individually hit RC 76 |
| Kimi K3 | P2 | `operatorOverride` as an in-workspace file a prior chunk could rewrite to steer the operator toward the orchestrator | Fixed: outside workspace, remove-only, annotations never rendered |
| Kimi K3 | P2 | No cross-provider-family exclusion for authorized review lanes | Fixed |
| Kimi K3 (final) | P2 | Nothing anchored `routing-policy.json`; the whole object could be reverted green | Fixed: 4 policy anchors added |
| GLM + Fable + Kimi | P3 x8 | attemptedProvider omission, ambiguous rail names, two-writer receipts, undefined "unanswered", RC 76 exit collapse, alias not anchored, `ask_evidence_ref` anchor satisfiable by the JSON literal, section label | All fixed |

- Regressions shipped by cheaper models: **none**. Every lane's findings were
  reviewed before application; no finding was applied blind.
- Retries: 1 (OpenRouter stream failure on the security recheck; succeeded on
  attempt 2 with the same model). Recorded as a failed attempt.
- Cap descents: 1 (Codex -> native rung, via the cascade).

## Kernel reliability

- Shadow: available. Prediction sealed pre-`run.started`; verification contract
  bound (revision 1) against a `not_declared` verification profile.
- Terminal parity: **gap** -- `missing_authoritative_evidence` /
  `missing_receipt_transition`. Cause is a genuine prediction shortfall: 13
  predicted receipts against 21 authoritative, because the prediction did not
  anticipate 5 review-lane attempt records or the real OpenRouter usage rows.
  Observation-only; it gated nothing.
- Browser recovery: not applicable (config chunk, no UI, no declared verification
  profile).
- Docker: no resources registered; nothing to reconcile.

## Recommendations (AWAITING APPROVAL -- proposal only, nothing auto-applied)

1. **Land the ask gate and use it.** This run is itself the fourth consecutive
   single-rail incident. The change under review is the fix. Expected delta: a
   capped-rail run stops producing zero-chunk terminal receipts.
   Confidence: high. Evidence: this run's own cascade RC 64 descent.
2. **Predict review lanes in the prediction stream.** The parity gap was caused
   entirely by not predicting review-lane attempt records. Adding them to the
   pipeline's prediction template would make parity meaningful instead of
   structurally guaranteed to gap. Expected delta: parity `match` becomes
   achievable. Confidence: high.
3. **Wire the Workflow Authority broker (R3).** Recurrence: this is the third
   ledger entry naming the missing broker (2026-08-07, 2026-08-08 R1, this run).
   **Promote to Standing Recommendation** -- three runs, citations
   `docs/pipeline-metrics/ledger.md` rows 2026-08-07 and 2026-08-08.
   Expected delta: restores the OpenRouter automated rail, removing the single
   largest source of routing variance in the last three runs.
4. **`security-auditor-codex-signoff` needs a declared behavior when Codex is
   capped.** It is `required: true` with no stated fallback, so today it silently
   becomes a coverage gap. The ask gate this run adds is the natural mechanism.
   Confidence: medium.
