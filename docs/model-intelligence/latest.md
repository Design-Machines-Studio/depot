# Depot model intelligence — 2026-08-27

## Evidence coverage

- Run cost summaries: 3
- Workflow metrics: 3
- Empty cost summaries: 2
- Benchmark attempts: 8
- Incomplete benchmark attempts: 2

## Production economics by model

| Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Cost | Finding contributions |
|---|---:|---:|---:|---:|---:|---:|---:|
| moonshotai/kimi-k3 | 4 | 5331.0s | 156997 | 157616 | 0 | $2.8345 | 0 |
| z-ai/glm-5.2 | 1 | 300.0s | 20394 | 30209 | 0 | $0.1615 | 0 |

## Production economics by lane and model

| Lane | Model | Attempts | Duration | Input tokens | Output tokens | Input bytes | Cost |
|---|---|---:|---:|---:|---:|---:|---:|
| 01-openrouter-usage-translator | moonshotai/kimi-k3 | 1 | 431.0s | 24410 | 39601 | 0 | $0.6671 |
| 02-lane-input-bytes | moonshotai/kimi-k3 | 1 | 400.0s | 16158 | 40837 | 0 | $0.6609 |
| 03-emission-contract-and-baselines | z-ai/glm-5.2 | 1 | 300.0s | 20394 | 30209 | 0 | $0.1615 |
| adversary-r1 | moonshotai/kimi-k3 | 1 | 3600.0s | 52660 | 35579 | 0 | $0.6915 |
| adversary-r2 | moonshotai/kimi-k3 | 1 | 900.0s | 63769 | 41599 | 0 | $0.8151 |

## Production quality signals

- Canonical findings: 0
- Median completion rate: 1.0
- Median fallback rate: 0.1
- Median first-pass validation rate: 0.0
- Retry reasons: `{"cascade_exhausted": 1, "codex_usage_cap": 5}`

These are workflow signals, not direct causal model-quality scores. Missing model attribution remains missing.

## Controlled benchmarks

| Model | Transport | Case | Success | Median quality | Median duration | Median cost |
|---|---|---|---:|---:|---:|---:|
| claude-fable-5 | claude-cli | assembly-next-chunk | 1/1 | 15.0 | 10.0s | n/a |
| gpt-5.6-luna | codex-cli | mechanical-owned-edit | 1/1 | 50.0 | 26.0s | n/a |
| gpt-5.6-luna | codex-cli | pipeline-legacy-translation | 1/1 | 35.0 | 14.0s | n/a |
| gpt-5.6-luna | codex-cli | review-zero-deferral | 3/3 | 100.0 | 6.0s | n/a |

## Interpretation limits

- Token counts and deterministic input bytes are different units and are never added together.
- Subscription API-equivalent cost is opportunity-cost evidence, not billed spend.
- A model-role change requires three successful attempts on every applicable local case plus production evidence; incomplete coverage cannot promote a model.
- Exact identity remains in private receipts; this report publishes aggregates only.
