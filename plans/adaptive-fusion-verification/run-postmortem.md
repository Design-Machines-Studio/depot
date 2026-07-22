# Run Post-Mortem: adaptive-fusion-verification

Date: 2026-07-22

## providerSplit

- Implemented chunks: `{claude: 0, codex: 6, openrouter: 0}` or `0% / 100% / 0%`.
- Provider token totals: unavailable; this host did not expose per-chunk Codex token receipts.
- Provider cost totals: unavailable; no Codex billing receipt or OpenRouter usage object was produced.

## eligibleProviderSplit

- Active subscription profile: `codex-20x`.
- Configured coding target: `{codex: 65%, openrouter: 35%}`.
- After provider-unavailable exclusions: `{codex: 3 chunks, 100%; openrouter: 0 chunks, 0%}`.
- Three OpenRouter-requested chunks were excluded after the provider declined export under tenant policy.

## routingExclusions

| Chunk | Excluded provider | Reason | Evidence |
|---|---|---|---|
| `03-authoritative-pipeline-feedback` | openrouter | provider-unavailable | `receipts/03-authoritative-pipeline-feedback.json` |
| `04-review-synthesis-provenance` | openrouter | provider-unavailable | `receipts/04-review-synthesis-provenance.json` |
| `06-cross-plugin-release-integration` | openrouter | provider-unavailable | `receipts/06-cross-plugin-release-integration.json` |

No security, required-live-tool, or quality-floor exclusion occurred.

## routingVariance

- Eligible actual minus target: Codex `+35 percentage points`; OpenRouter `-35 percentage points`.
- Receipt-backed reason: all three requested OpenRouter lanes were declined before export (`tenant-policy-denied`) and used explicit Codex fallback. The six-chunk sample is also too small to express a 65/35 target exactly.

## measurementSources

- Claude JSONL delta: not applicable; Claude executed no coding lane.
- `ccusage blocks --json`: not applicable.
- Codex `tokens used`: unavailable from the per-chunk receipts in this host.
- OpenRouter API `usage`: none; export was declined before model execution.
- Estimated fallback: none. Unknown token and cost values remain unknown rather than fabricated.
- Timing source: first and terminal authoritative receipt timestamps. No typed wait receipts were emitted, so elapsed inter-turn time cannot be separated from active work.

## routingTargetComparison

| Measure | Codex | OpenRouter |
|---|---:|---:|
| `codex-20x` target | 65% | 35% |
| Eligible actual | 100% | 0% |
| Variance | +35 pp | -35 pp |

The variance is diagnostic only and does not change routing authority.

## misroutes

None. Claude executed no coding task. OpenRouter-requested lanes have explicit unavailable/fallback receipts rather than silent rerouting.

## qualityLedger

- Codex implemented all six chunks and all bounded review/fix iterations.
- Final full review used three Codex lenses because OpenRouter export was unavailable. The lenses found and resolved contract-path drift, regression-proof gaps, decision-profile continuity loss, ambiguous metric aggregation, intervention identity conflicts, shell-command parsing bypasses/false positives, and durable credential-detection gaps.
- Final state: three clean re-reviews, zero unresolved or deferred P1/P2 findings.
- Evaluation iterations by chunk: `01:2`, `02:2`, `03:2`, `04:3`, `05:3`, `06:1`.
- Cap descents: none recorded. Human intervention: none recorded. Regressions shipped by a cheaper model: none; OpenRouter did not execute.

## rankedRecommendations

### AWAITING APPROVAL: Preserve shadow compatibility across self-hosting upgrades

- Plugin/file: `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py`
- Concrete edit: version or migrate the pre-feature RunSpec contract used by shadow observation so a run that upgrades its own adapter does not become unobservable solely because the new contract was not available at initialization.
- Expected token/cost delta: bounded reduction in repeated failed observation attempts; exact tokens unavailable.
- Confidence: high
- Evidence: `pipeline-shadow-observation.json`, `execution-ledger.md`

### AWAITING APPROVAL: Publish canonical verification launch commands

- Plugin/file: `plugins/pipeline/agents/workflow/execution-orchestrator.md`
- Concrete edit: make generated verification commands include the canonical launcher or required `PYTHONPATH` rather than a bare repository-local unittest invocation.
- Expected token/cost delta: small reduction in diagnosis/retry work; exact tokens unavailable.
- Confidence: high
- Evidence: `final-requirements-crosscheck.md`

### AWAITING APPROVAL: Split live sibling declarations from Depot-owned release gates

- Plugin/file: `tools/validate-workflow-kernel.py`
- Concrete edit: retain fail-closed sibling declaration validation in a separately named integration lane while keeping Depot-owned deterministic release results independently visible.
- Expected token/cost delta: no expected quality reduction; faster root-cause isolation.
- Confidence: medium
- Evidence: final 786-test run and `final-requirements-crosscheck.md`

## standingRecommendations

None. No recommendation in the rolling ledger has reached the default three-run promotion threshold.

## kernelReliability

- Shadow availability: prediction bound successfully; later observation became unavailable after the run hot-upgraded its own adapter contract.
- Semantic parity status: unavailable/unsafe to compare; no parity match is claimed.
- Comparison reasons: adapter contract mismatch for the pre-feature run; authoritative Markdown receipts remained canonical.
- Observation/adapter failures: one recurring self-hosting compatibility failure after chunk 02.
- Missing authoritative evidence: none for dispatch, validation, evaluation, merge, review, or cleanup.
- Browser recovery outcomes: not applicable because no UI/browser chunk ran; the recovery contract and tests passed.
- Owned-resource cleanup: six chunk receipts and terminal reconciliation all show zero created, removed, retained, or blocked Docker resources.
- Reconciliation: complete for current run and stale sweep; exact managed inventory was empty.

## workflowClass

- `workflow_class`: `feature`
- `workflow_class_defaulted`: `false`

## providerReceipts

| Chunk/lane | Requested | Attempted | Implemented by | Fallback | Reason |
|---|---|---|---|---|---|
| `01-behavioral-contract-core` | codex | codex | codex | false | none |
| `02-contract-policy-integration` | codex | codex | codex | false | none |
| `03-authoritative-pipeline-feedback` | openrouter | codex | codex | true | tenant-policy-denied |
| `04-review-synthesis-provenance` | openrouter | codex | codex | true | tenant-policy-denied |
| `05-attempt-economics-and-contribution` | codex | codex | codex | false | none |
| `06-cross-plugin-release-integration` | openrouter | codex | codex | true | tenant-policy-denied |
| final full review | openrouter + codex | codex | codex | true | OpenRouter tenant-policy-denied; three Codex lenses ran |

## wallClockSeconds

`16172` seconds, from `2026-07-22T02:53:35Z` to `2026-07-22T07:23:07Z`.

## activeComputeSeconds

`16172` seconds by the required formula. This is an upper bound because no typed wait receipts were available to subtract inter-turn wait time.

## waitSecondsByCategory

`{human_gate: 0, external_dependency: 0, capacity: 0, ci: 0}` from authoritative wait receipts. No such receipts were emitted; this does not prove that no wall-clock waiting occurred.
