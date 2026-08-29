# Assembly Baseplate federation architecture prototype

Run date: 2026-08-28 (Asia/Makassar)

Baseplate evidence revision: `f527fdf4b69725d73ed4ba01a3b4903a6b694211`

Sealed prompt SHA-256: `1e749af4b2ada634f13a588b6f6435218a49826f80ebc268e57e1baf0a5345d1`

## Scenario

Candidates designed a bounded way for sovereign 4-50-user Baseplate installs
to observe federation compatibility. The evidence covered identity, protocol
and capabilities, Assembly-info, trust delivery, HTTP security, state models,
and update health/handoff/orchestration. The answer had to address pull versus
push, data and state, backward compatibility, trust, offline behavior, update
truth, rollback, operator experience, verification, and delivery slices.

The exact source selectors and missing reproducibility boundary are preserved
in `depot-role-portfolio.json` and `depot-role-baseplate-cases.md`.

## Retained attempts

Every listed candidate completed three attempts and retained no model fallback.
OpenRouter response identity matched the requested model on all paid attempts.

| Candidate / transport | Attempts | Median duration | Median completion tokens | Provider-billed/API-equivalent total |
|---|---:|---:|---:|---:|
| DeepSeek V4 Flash 0731 / OpenRouter | 3 | 132.03s | 21,960 | $0.01265354524 billed |
| DeepSeek V4 Pro 0813 / OpenRouter | 3 | 287.00s | 15,736 | $0.097017352872 billed |
| GLM 5.3 Flash / OpenRouter | 3 | 348.30s | 15,201 | $0.01452967 billed |
| Kimi K3 / OpenRouter | 3 | 524.89s from two timed receipts | 6,216 | $0.37849082 billed |
| Qwen3.8 Max / OpenRouter | 3 | 442.86s | 16,512 | $0.384138 billed |
| Fable / native Claude | 3 | 142.33s | 10,377 | $0 marginal; $3.509015 API-equivalent reported |
| Opus alias / native Claude | 3 | 75.78s | 5,255 | $0 marginal; $1.4382325 API-equivalent reported |

Native Claude cost values are retained as API-equivalent telemetry, not
provider-billed subscription spend. The first Kimi timing file was absent, so
its duration coverage is incomplete.

## Evidence limitation

The run retained the prompt hash, candidate plan, raw output, and receipts, but
did not retain the exact deterministic scorer beside the run. Proceeding to
three attempts indicates that the contemporaneous screen considered the
outputs complete, but that is not reproducible closed quality evidence.

The outputs therefore remain useful for refining the case and comparing
latency, tokens, cost, identity, and fallback behavior. They must not promote,
demote, or rank model quality. T3 should reconstruct and seal the missing
scorer, then run a new case revision rather than retroactively grading these
outputs with a newly invented contract.

**No routing change justified.**
