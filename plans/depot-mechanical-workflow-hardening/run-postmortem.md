# Run Post-Mortem: depot-mechanical-workflow-hardening

Date: 2026-07-22

## providerSplit

- Implemented chunks: `{claude: 0, codex: 8, openrouter: 0}` or `0% / 100% / 0%`.
- Requested/attempted dispatches: seven Codex chunks and one OpenRouter chunk. The OpenRouter attempt was rejected by the host privacy boundary before export; no repository content left the machine and Codex completed the chunk through an explicit fallback receipt.
- Provider token totals and costs: unavailable. The host exposed neither per-chunk Codex token receipts nor a successful OpenRouter usage object. Unknown values remain unknown rather than being replaced with zero or estimates.

## eligibleProviderSplit

- Active subscription profile: `codex-20x` (`65%` Codex / `35%` OpenRouter among eligible coding chunks).
- Eligible actual after the privacy/tool exclusion: `{codex: 7 chunks, 100%; openrouter: 0 chunks, 0%}`.
- Chunk `06-assembly-repository-profile` is excluded from the eligible denominator because the provider security boundary rejected the required private workspace export before execution.

## routingExclusions

| Chunk | Excluded provider | Category | Evidence-backed reason |
|---|---|---|---|
| `06-assembly-repository-profile` | OpenRouter | security/tool boundary | The host rejected private prompt/workspace export before export; `receipts/06-assembly-repository-profile.json` records requested, attempted, fallback, implementer, and reason. |

No quality-floor exclusion or silent provider substitution occurred.

## routingVariance

- Eligible actual minus target: Codex `+35 percentage points`; OpenRouter `-35 percentage points`.
- Reason: the only OpenRouter-requested chunk was excluded by the privacy boundary, leaving seven Codex-fixed logic/integration chunks. An eight-chunk run is also too small to express the target exactly.
- The variance is observation only and does not change routing authority.

## measurementSources

- Claude JSONL delta: not applicable to coding; Claude implemented no chunk.
- Codex `tokens used`: unavailable from the chunk receipts on this host.
- OpenRouter API usage/cost: unavailable because the provider attempt stopped before export or model execution.
- Wall-clock and active-compute totals: unavailable as reliable run-scoped measures. Authoritative event times capture workflow milestones, but the run did not emit complete non-overlapping typed-wait receipts, so active compute cannot be separated honestly from inter-turn time.
- Typed waits: unavailable, not zero.

## misroutes

None. Every chunk was dispatched according to the manifest or used an explicit, reasoned fallback. No `executor: codex|openrouter` chunk was silently implemented in the orchestrator process.

## qualityLedger

- Per-chunk independent review iterations: `01:2`, `02:3`, `03:2`, `04:6`, `05:3`, `06:3`, `07:4`, `08:2`.
- The final architecture review found two P1 trust-boundary defects: verification execution trusted caller-authored repository state, and read-only review evidence accepted an unsafe caller-selected exclusion without stable launcher capture/compare commands.
- The zero-deferral repair added live repository capture at spawn time, EventStore-rooted content-addressed review boundaries, physical identity checks, stable launcher commands, release-inventory checks, and hostile regression coverage.
- Final repair verification: 109 focused tests passed. The complete repair suite ran 894 tests with zero Depot-owned failures and one skip. Its only error is a live sibling `assembly-baseplate` UX/persona declaration that fails the strict declaration adapter; this branch did not modify or relabel that external state.
- No cheaper-model regression shipped: OpenRouter did not execute repository code.

## kernelReliability

- Workflow class: `feature`; not defaulted.
- Shadow mode remained observation-only and never changed Pipeline authority.
- The first all-chunks observation consumed 49 authoritative events but did not establish a usable prediction binding in the observation result. The pre-start 52-event prediction artifact is retained. No after-the-fact rebinding was attempted.
- Final semantic parity is expected to remain a visible `missing_authoritative_evidence` or `kernel_prediction_gap` unless the terminal comparison can prove the original binding.
- Browser execution: not declared for these backend/plugin chunks. Browser recovery rules, persona discovery, scenarios, and evidence bundles are covered by deterministic tests.
- Chunk Docker inventories: eight exact-label checks, all empty; no broad prune was used.

## providerReceipts

| Chunk | Requested | Attempted | Implemented by | Fallback |
|---|---|---|---|---|
| `01-repository-verification-foundation` | codex | codex | codex | no |
| `02-artifact-safety-and-staging` | codex | codex | codex | no |
| `03-browser-scenarios-and-bundles` | codex | codex | codex | no |
| `04-read-only-review-and-findings` | codex | codex | codex | no |
| `05-ci-evidence-and-closeout` | codex | codex | codex | no |
| `06-assembly-repository-profile` | openrouter | openrouter | codex | yes: host privacy boundary before export |
| `07-pipeline-integration-and-scout` | codex | codex | codex | no |
| `08-cross-plugin-release-integration` | codex | codex | codex | no |

## rankedRecommendations

### AWAITING APPROVAL: Split live sibling declaration compatibility from Depot-owned release results

- Plugin/file: `tools/validate-workflow-kernel.py` and the composition wrapper.
- Concrete edit: retain the fail-closed live sibling adapter check, but report it as a separately named integration boundary alongside an independently visible Depot-owned unit/release result.
- Expected token/cost delta: exact savings unavailable; expected benefit is faster root-cause isolation without weakening the sibling compatibility gate.
- Confidence: high.
- Evidence: the same recommendation appears in `plans/adaptive-fusion-verification/run-postmortem.md`; the current 894-test run again has zero owned failures and exactly one live sibling declaration error.

### AWAITING APPROVAL: Add an immediate shadow-binding self-check

- Plugin/file: Pipeline shadow initialization around `bind-prediction` and the Workflow Kernel observation report.
- Concrete edit: immediately verify the sealed lifecycle binding before the first authoritative action and persist a small diagnostic receipt that distinguishes missing binding, mismatched state directory, and later adapter drift.
- Expected token/cost delta: unavailable; expected benefit is avoiding terminal diagnosis of a binding that was unusable from run start.
- Confidence: medium.
- Evidence: `pipeline-shadow-prediction.json` exists, while `pipeline-shadow-observation.json` contains the 49-event observation without a usable bound-prediction assertion.

## standingRecommendations

None. The sibling-boundary recommendation has recurred in two runs, below the default standing threshold of three.

## proposalOnly

All recommendations above are `AWAITING APPROVAL`. This post-mortem does not mutate routing policy, plugin sources, releases, PR state, or installed caches.
