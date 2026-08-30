# Model Selection

OpenRouter model evidence and executable routing are deliberately separate.
`model-matrix.json` records provider-specific catalog, pricing, feature, and
quality evidence. Cross-transport candidate ordering lives only in
model-router's private `role-policy.json`; Pipeline, dm-review, and project
coordination request roles without reading this matrix.
`quality_rank` remains a compatibility and quality-floor field, not a scoring
engine.

## Available Models

Prices below are a checked-in planning snapshot from 2026-08-27, in USD per
million input/output tokens. The compact refresh receipt is
`docs/openrouter-model-matrix-refreshes/2026-08-27.md`; use a fresh catalog
receipt before a later paid or policy-changing run.

| Exact slug | Input / output | Context | Catalog evidence |
|---|---:|---:|---|
| `deepseek/deepseek-v4-flash-0731` | $0.06 / $0.12 | 1,310,720 | Low-cost bounded reasoning/tools/structured output |
| `deepseek/deepseek-v4-pro-0813` | $1.122 / $3.366 | 1,048,576 | Historical v1: three corrected pipeline attempts at 100/100; incompatible single-case evidence only |
| `qwen/qwen3.8-max` | $2 / $6 | 1,000,000 | Long-context independent analysis evidence |
| `qwen/qwen3.8-2.4t-a95b` | $2 / $6 | 1,048,576 | Catalogued; no active consumer |
| `qwen/qwen3.8-27b` | $0.425 / $2.55 | 1,000,000 | Catalogued; no active consumer |
| `qwen/qwen3.7-flash` | $0.03 / $0.13 | 1,000,000 | Catalogued; no active consumer |
| `x-ai/grok-4.6` | $2 / $6 | 500,000 | Demanding bounded reasoning and distinct-family evidence |
| `google/gemini-3.7-flash` | $0.375 / $1.875 | 1,048,576 | Fast multimodal/tools/web-search evidence |
| `meta/muse-spark-1.2` | $1.25 / $4.25 | 1,048,576 | Catalogued; no text-only active consumer |
| `z-ai/glm-5.3` | $1.40 / $4.40 | 1,048,576 | Catalogued-not-routed; mandatory reasoning defaults to max |
| `z-ai/glm-5.3-flash` | $0.075 / $0.25 | 1,310,720 | Historical v1: formerly Ox Alpha; three corrected pipeline attempts at 100/100; incompatible single-case evidence only |
| `moonshotai/kimi-k3` | $3 / $15 | 1,048,576 | Focused security-analysis evidence at high cost |
| `openai/gpt-5.6-luna` | $0.20 / $1.20 | 1,050,000 | Economical mechanical-analysis evidence |
| `openai/gpt-5.6-terra` | $2 / $12 | 1,050,000 | Catalogued compatibility evidence; no default role |

Every executable identity is an exact versioned slug. Moving aliases such as
`latest` are forbidden. GLM 5.3 is recorded only as the exact catalog identity
`z-ai/glm-5.3` / canonical `z-ai/glm-5.3-20260816`; it has no default role.
The matrix records cache pricing, top-provider limits, feature support,
benchmark provenance, and missing values without inference.

Native Codex identities and native Claude aliases are not OpenRouter routing
models. OpenRouter transport is provider provenance, not a model family;
independent-family checks use the selected model family. `anthropic/*` slugs
remain prohibited on this rail.

## Refreshing the routing matrix

Refresh the official OpenRouter catalog once per evidence run and create a
dated receipt with `observedAt` and `expiresAt` no more than 15 minutes apart.
Update the top-level routing `snapshot_date` and every `models[*].snapshot_date`
together. Record unavailable facts as unavailable, retain older comparable
benchmark values only with explicit provenance, and never infer a new model's
quality from another version. A matrix refresh does not route a model until
model-router's policy explicitly selects its exact slug and the drift validator
confirms that slug still exists here.

## Refreshing native API-equivalent cost evidence

Native cost evidence is observation-only and has its own snapshot. Refresh it
only from the named official source, without restamping it during a routing
refresh. Native aliases never become OpenRouter candidates merely because they
can be assigned an API-equivalent planning cost.

## Catalog eligibility

This file may explain evidence for an OpenRouter model's capabilities, price,
context, and provider behavior, but it does not assign Pipeline or dm-review
lanes. model-router owns role ordering, family exclusion, cross-transport
fallback, and live availability. Input eligibility is provider-neutral:
OpenRouter receives any prompt/evidence an eligible native Claude/Codex
candidate may receive. OpenRouter still rejects malformed request envelopes
and validates transport responses, but never rejects payload content under a
provider-only rule.

## Provider privacy

Provider privacy follows quality, price, and speed in the routing priority.
`OPENROUTER_ZDR=1` is opt-in and restricts a call to endpoints whose data policy
denies training and retention; use it for genuinely sensitive eligible material.
If ZDR leaves no eligible Kimi endpoint, the ordered security fallback may serve Grok 4.6.
See `invocation-protocol.md` for the complete
provider-routing controls and receipt behavior.

## Direct delegation topology

The direct user-facing `/openrouter --model` override remains an explicit
operator choice. Its default wrapper fallback may remain provider-specific and
is not consumed by Pipeline, dm-review, or Assembly coordination. Routed
workloads pass one exact resolver-selected candidate to the wrapper; a provider
failure returns to model-router for the next role candidate with a separate
attempt receipt.

## Depot role benchmark

Public benchmarks do not reproduce Depot's prompts, role contracts, request
shape, or verification rules. `depot-role-benchmark.md` defines a bounded
local complement: `depot-role-v2` has 18 distinct cases covering all nine roles,
stage-attributed failures, raw and normalized output, digest-bound evaluator
cohorts, confirmed requested/served identity provenance, deterministic scoring,
and exact one-model runs. It is an explicit operator measurement surface and
never becomes a provider-bearing orchestration prompt. Screens nominate
opportunities only. Promotion requires three comparable successful attempts on
every applicable distinct case plus current production and policy gates.

Interpret current evidence quality-first: validated case quality, first-pass
reliability, rework/time to valid, latency, context and telemetry coverage, and
production signals precede provider spend and access economics. Benchmark-owned
prompt, parser, scorer, binding, or harness faults and incompatible digests have
no model conclusion; retain them, stop calls, repair locally, and validate the
harness before collecting new evidence. The optional blind editorial receipt is
a separate nullable human-quality axis, never a deterministic or model-judge
gate. Artificial Analysis Optima remains an optional manual hosted surface;
Depot does not depend on it or automate its spend.

## Historical v1 evidence interpretation

The evidence below was produced by the retired `depot-role-v1` contract. It is
dated historical evidence, incompatible with v2 evaluator cohorts, and cannot
support a current model conclusion or promotion without new v2 coverage.

The 2026-08-25 refresh made no model inference call. Artificial Analysis Coding
Agent Index v1.4 is a three-harness pass@1 composite, not a universal Depot
ranking. OpenRouter rankings measure public token adoption, not quality, and
exclude private and ZDR activity. DeepSeek V4 Flash 0731's very low measured
cost and second-place OpenRouter usage reinforce its bounded-work candidacy,
while its lower index and middling task time argue against treating it as a deep
reasoning default. Gemini 3.7 Flash remains the fast research head. Kimi remains
focused on security because its strong score came with high time and cost.
Historical GLM 5.2 evidence is retained but is not transferred to either exact
GLM 5.3 variant.

Ox Alpha was revealed as the exact live identity `z-ai/glm-5.3-flash`; it is
catalogued for the local suite but not routed. Two initial HTTP 429 attempts
exposed benchmark tooling that conflated model fallback with same-model provider
fallback. A third attempt exposed an under-specified prompt. A fourth and a
DeepSeek control both returned the requested chunk directly, proving that the
prompt still failed to require the top-level `chunks` envelope. Those results
are retained but not comparable.

After OpenRouter 1.19.9 made the complete prompt contract explicit, three exact
`z-ai/glm-5.3-flash` attempts scored 100/100 with no model fallback. Their
comparable medians were 5 seconds, 160 prompt tokens, 155 completion tokens,
111 reasoning tokens, and $0.0000975 provider-billed cost. The three other
applicable cases and production canary remain untested, so GLM 5.3 Flash is not
routed.

After OpenRouter 1.19.9 made that envelope explicit, three exact
`deepseek/deepseek-v4-pro-0813` attempts scored 100/100 with no model fallback.
Their comparable medians were 6 seconds, 163 prompt tokens, 258 completion
tokens, 195 reasoning tokens, and $0.00123684 provider-billed cost. This
single-case control validates the repaired harness but does not change routing.
MiMo-V2.5, Hy3, Nemotron 3 Ultra, and DeepSeek V4 Pro 0423 remain candidates
without exact Depot evidence. The Coding Agent Index score for Grok 4.5 is not
assigned to Grok 4.6.

The recent Baseplate operator evidence also matters: Kimi was repeatedly used
for ordinary review at substantial cost, Luna handled routine lanes cheaply,
and DeepSeek was never reached. The repaired ordered policies—not the matrix
rank—now make DeepSeek and Qwen reachable while restricting Kimi to security.

## Direct wrapper fallback behavior

The wrapper accepts an exact primary and optional exact fallback slug as one
ordered `models` array. Direct delegation defaults to:

```text
qwen/qwen3.8-max -> x-ai/grok-4.6
```

Security is the sole Kimi route:

```text
moonshotai/kimi-k3 -> x-ai/grok-4.6
```

Pass exactly one model slug and no fallback slug for a measured one-model call.
Leave same-model provider fallback enabled so a transient endpoint failure does
not invalidate the candidate. Receipts must record requested and returned models,
model fallback, and provider-fallback policy as separate evidence.
