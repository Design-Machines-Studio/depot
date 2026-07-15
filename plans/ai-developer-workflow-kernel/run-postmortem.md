# Pipeline Run Post-Mortem: AI Developer Workflow Kernel

- Date: 2026-07-15
- Run: `ai-developer-workflow-kernel`
- executionMode: `codex_native`
- Workflow class: `feature`
- workflow_class_defaulted: `false`
- Measurement boundary: this implementation run predates an initialized workflow-kernel shadow state; fixture evidence is not treated as real-run telemetry.

## providerSplit

| Provider | Routed chunks | Actual implementation | Tokens | Cost |
|---|---:|---:|---:|---:|
| claude | 2 | 0 | unavailable | no API receipt |
| codex | 4 | 6 | unavailable | unavailable |
| openrouter | 0 | 0 | 0 observed | $0 observed |
| deepseek | 0 | 0 | 0 observed | $0 observed |

Actual implementation split by chunk was Codex 100%, Claude 0%, OpenRouter 0%, and DeepSeek 0%. Token and cost totals are not estimated because the Codex desktop run exposed no durable per-provider usage receipt.

## measurementSources

- Chunk receipts 01–06: `implementedBy: codex`, `fallback: none`.
- Manifest executor targets: chunks 01–04 Codex; chunks 05–06 Claude.
- Codex `tokens used`: unavailable in the durable task output.
- Claude JSONL delta and `ccusage blocks --json`: unavailable; no Claude execution receipt was produced.
- OpenRouter/DeepSeek API `usage`: none observed; neither provider was dispatched.
- Estimates: none. Unknown values remain `unavailable`.

## routingTargetComparison

- Configured target: Codex 4 chunks, Claude 2 chunks, OpenRouter 0, DeepSeek 0.
- Actual: Codex 6 chunks, Claude 0, OpenRouter 0, DeepSeek 0.
- Variance: two integration chunks assigned to Claude in the manifest were implemented directly by Codex.
- Interpretation: this is a receipt-visible routing variance, not evidence that the result was lower quality. The full behavioral and composition gates passed.

## misroutes

| Lane | Policy target | Actual | Token cost | Required follow-up |
|---|---|---|---|---|
| `05-shadow-workflow-adapters` | claude | codex | unavailable | Record `requested`, `attempted`, `implementedBy`, and reason in every chunk receipt. |
| `06-hardening-promotion-release` | claude | codex | unavailable | Record `requested`, `attempted`, `implementedBy`, and reason in every chunk receipt. |

No source routing policy is changed by this post-mortem.

## qualityLedger

- All six chunk receipts report Codex implementation and zero deferred findings.
- Chunk review/evaluation iterations: 37, 25, 18, 26, 8, and 6 respectively (120 total recorded chunk iterations).
- The first final holistic Codex review found one ordinary-state publication integrity issue and terminal evidence/progress gaps. The state issue was repaired at `916f10e`; the evidence gap was closed in `final-requirements-crosscheck.md`.
- Final verification after repair: 692 Python 3.12 tests passed with one expected opt-in live-Docker skip; all 13 behavioral validator sections passed; full composition validation passed.
- No regression is known to have shipped from a cheaper or fallback model. No external-provider review receipt exists for comparison.

## rankedRecommendations

### AWAITING APPROVAL: Make provider receipts complete at chunk creation

- Plugin/file: `plugins/pipeline/agents/workflow/execution-orchestrator.md`
- Concrete edit: require `requested`, `attempted`, `implementedBy`, `fallback`, and reason fields in every chunk receipt, including same-provider and unavailable cases.
- Expected token/cost delta: negligible receipt overhead; enables measured routing variance and cost attribution.
- Confidence: high
- Evidence: `plans/ai-developer-workflow-kernel/manifest.json`; receipts 05 and 06.

### AWAITING APPROVAL: Persist harness token counters into the run receipt

- Plugin/file: `plugins/pipeline/references/run-postmortem-schema.md`
- Concrete edit: define a Codex-desktop usage source and explicit unavailable reason code so providerSplit is machine-readable without estimates.
- Expected token/cost delta: none in execution; small receipt size increase.
- Confidence: medium
- Evidence: this run has no durable Codex token or cost counter despite six implemented chunks.

### AWAITING APPROVAL: Audit high review-iteration runs for repeated signatures

- Plugin/file: `plugins/pipeline/agents/workflow/execution-orchestrator.md`
- Concrete edit: after ten review iterations, emit a proposal-only convergence diagnostic grouping repeated root causes; do not weaken zero-deferral gates.
- Expected token/cost delta: likely lower on runs with repeated findings; unmeasured here.
- Confidence: medium
- Evidence: 120 recorded chunk review/evaluation iterations in this run.

## standingRecommendations

None. This is the first cited run for each recommendation; the standing threshold remains three runs.

## kernelReliability

- Shadow availability: implemented and validator-proven; no authoritative real shadow run exists for this pre-kernel implementation run.
- Semantic parity: fixture parity passed; real-run parity status unavailable.
- Comparison reasons: no real-run comparison receipt; fixture-only release evidence sets `real_run_evidence: false`.
- Observation/adapter failures: none in offline validation.
- Missing authoritative evidence: real browser, live-Docker, real shadow-parity, token, and cost receipts are unavailable and are not inferred.
- Browser recovery: 0 real attempts; full primary-restart, alternate-engine, and human-help grammar passed behavioral tests.
- Personas: Assembly and assembly-baseplate layouts passed discovery and blocking-gate tests; no product browser session was run for this logic/integration feature.
- Owned resources: no workflow-labeled Docker resource was created or found during chunk inventories.
- Reconciliation: terminal current-run and managed stale-sweep inventories each found zero containers, networks, or volumes. Kernel-native reconciliation is unavailable because this run has no initialized repository-scope registry.

## providerReceipts

| Lane | Requested | Attempted | Implemented by | Fallback | Reason |
|---|---|---|---|---|---|
| 01 kernel state | codex | codex | codex | none | manifest target available |
| 02 policy/hosts | codex | codex | codex | none | manifest target available |
| 03 resources | codex | codex | codex | none | manifest target available |
| 04 persona/browser | codex | codex | codex | none | manifest target available |
| 05 shadow adapters | claude | codex | codex | unrecorded | Codex-native run produced no Claude attempt receipt |
| 06 release | claude | codex | codex | unrecorded | Codex-native run produced no Claude attempt receipt |

These reconstructed provider rows are derived from the manifest and chunk receipts; the missing attempt reasons are reported as gaps rather than fabricated.
