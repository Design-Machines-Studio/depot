# Depot model intelligence — 2026-08-29

## Per-role validated quality and efficiency

| Role | Cases | Validated | Best quality | First pass | Median duration | Time to valid | Attempts/rework | Confidence | Freshness | Gap |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| architect | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| plan-critic | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| builder-fast | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| builder-deep | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| review-fast | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| review-deep | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| security-review | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| research-fast | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |
| editorial | 0/2 | n/a | n/a | n/a | n/a | n/a | n/a | none | none | no comparable current evidence |

Missing ordering, duration, token, cache, context, tool, correction, and finding telemetry stays null. Independent repeated attempts do not imply an in-session tool call or correction loop.

## Role case coverage and instrumentation

### architect

- Missing cases: assembly-next-chunk, architect-routing-tradeoff
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### plan-critic

- Missing cases: plan-approved-scope-audit, plan-contradiction-repair
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### builder-fast

- Missing cases: pipeline-legacy-translation, mechanical-owned-edit
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### builder-deep

- Missing cases: builder-multifile-repair, builder-validation-feedback-repair
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### review-fast

- Missing cases: review-zero-deferral, review-false-positive-control
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### review-deep

- Missing cases: review-cross-file-invariant, review-validation-claims
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### security-review

- Missing cases: security-auth-boundary, security-release-integrity
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### research-fast

- Missing cases: research-claim-source-map, research-conflicting-evidence
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

### editorial

- Missing cases: editorial-member-update, editorial-release-note
- Operational retries: `{}`
- Model-attributable failures: `{}`
- Instrumentation coverage: `{"attempt_order": null, "cache_creation_tokens": null, "cache_read_tokens": null, "completion_tokens": null, "context_tokens": null, "correction_count": null, "duration_seconds": null, "false_positives": null, "prompt_tokens": null, "reasoning_tokens": null, "tool_calls": null, "useful_findings": null}`
- Policy snapshot: openrouter:2026-08-25; suite revision: 1

## Controlled model-role evidence

No attributable current v2 model-role evidence is available.

## Controlled reliability and failure attribution

No compatible v2 controlled groups were found.

- Incomplete attempts retained: 0
- Incompatible v2 attempts retained: 0
- Historical v1 attempts retained: 0
- Benchmark, prompt, parser, scorer, and harness faults have `no model conclusion` and do not enter model reliability or demotion evidence.

## Editorial blinded human evidence

No accepted blinded digest-matched editorial human evidence is available; human quality remains null.

## Production quality signals

- Canonical findings: 0
- Median completion rate: 1.0
- Median fallback rate: 0.1
- Median first-pass validation rate: 0.0
- Retry reasons: `{"cascade_exhausted": 1, "codex_usage_cap": 5}`

These are workflow signals, not direct causal model-quality scores. Missing model attribution remains missing.

## Capabilities and family diversity

Capabilities and model families are policy dimensions. They are not folded into quality, reliability, latency, tokens, or cost.

## Latency, tokens, context, and tools

Recorded duration, prompt/completion/reasoning/cache tokens, context, and tool telemetry remain independent axes. Coverage is reported above; missing values are not zero.

## Provider spend and access economics

- Benchmark provider-billed cost: None
- Benchmark recorded-cost coverage: `{"attempts": 0, "rate": null, "recorded": 0}`

| Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Provider-billed cost | Finding contributions |
|---|---:|---:|---:|---:|---:|---:|---:|
| moonshotai/kimi-k3 | 4 | 5331.0s | 156997 | 157616 | 0 | $2.8345 | 0 |
| z-ai/glm-5.2 | 1 | 300.0s | 20394 | 30209 | 0 | $0.1615 | 0 |

### Production economics by lane and model

| Lane | Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Provider-billed cost |
|---|---|---:|---:|---:|---:|---:|---:|
| 01-openrouter-usage-translator | moonshotai/kimi-k3 | 1 | 431.0s | 24410 | 39601 | 0 | $0.6671 |
| 02-lane-input-bytes | moonshotai/kimi-k3 | 1 | 400.0s | 16158 | 40837 | 0 | $0.6609 |
| 03-emission-contract-and-baselines | z-ai/glm-5.2 | 1 | 300.0s | 20394 | 30209 | 0 | $0.1615 |
| adversary-r1 | moonshotai/kimi-k3 | 1 | 3600.0s | 52660 | 35579 | 0 | $0.6915 |
| adversary-r2 | moonshotai/kimi-k3 | 1 | 900.0s | 63769 | 41599 | 0 | $0.8151 |

## Interpretation limits

- Token counts and deterministic input bytes are different units and are never added together.
- Subscription marginal cost, API-equivalent opportunity cost, and provider-billed spend remain separate views.
- A model-role change requires three successful attempts on every applicable local case plus production evidence; incomplete coverage cannot promote a model.
- Routing conclusion: no routing change justified.
