# Model Selection

OpenRouter model evidence and executable routing are deliberately separate.
`model-matrix.json` records current evidence; ordered role lists in Pipeline's
`routing-policy.json` and `harness-profile.json` are the routing authority.
`quality_rank` remains a compatibility and quality-floor field, not a scoring
engine.

## Available Models

Prices below are a checked-in planning snapshot from 2026-08-17, in USD per
million input/output tokens. The compact refresh receipt is
`docs/openrouter-model-matrix-refreshes/2026-08-17.md`; use a fresh catalog
receipt before a later paid or policy-changing run.

| Exact slug | Input / output | Context | Current role |
|---|---:|---:|---|
| `deepseek/deepseek-v4-flash-0731` | $0.14 / $0.28 | 1,048,576 | Primary cheap bounded executor; documentation and test review |
| `deepseek/deepseek-v4-pro-0813` | $0.66 / $1.98 | 1,048,576 | Provisional pattern and long-context analysis |
| `qwen/qwen3.8-max` | $2 / $6 | 1,000,000 | Bulk/independent review and complexity judgment |
| `qwen/qwen3.8-2.4t-a95b` | $2 / $6 | 1,048,576 | Catalogued; no active consumer |
| `qwen/qwen3.8-27b` | $0.45 / $3.20 | 262,144 | Catalogued; no active consumer |
| `qwen/qwen3.7-flash` | $0.03 / $0.13 | 1,000,000 | Catalogued; no active consumer |
| `x-ai/grok-4.6` | $2 / $6 | 500,000 | Demanding bounded escalation; independent security fallback |
| `google/gemini-3.7-flash` | $0.375 / $1.875 | 1,048,576 | Catalogued; no text-only active consumer |
| `meta/muse-spark-1.2` | $1.25 / $4.25 | 1,048,576 | Catalogued; no text-only active consumer |
| `z-ai/glm-5.2` | $0.76 / $2.42 | 1,048,576 | Evidence only; excluded from every active ladder |
| `moonshotai/kimi-k3` | $3 / $15 | 1,048,576 | Focused applicable security analysis only |
| `openai/gpt-5.6-luna` | $0.10 / $0.60 | 1,050,000 | Economical mechanical fallback |
| `openai/gpt-5.6-terra` | $1 / $6 | 1,050,000 | Catalogued compatibility evidence; no default role |

Every executable identity is an exact versioned slug. Moving aliases such as
`latest` are forbidden. GLM 5.3 was absent from the catalog at refresh time and
has no executable identity. The matrix records cache pricing, top-provider
limits, feature support, benchmark provenance, and local evidence without
inventing unavailable values.

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
quality from another version. A matrix refresh does not route a model until an
ordered consumer list explicitly selects it.

## Refreshing native API-equivalent cost evidence

Native cost evidence is observation-only and has its own snapshot. Refresh it
only from the named official source, without restamping it during a routing
refresh. Native aliases never become OpenRouter candidates merely because they
can be assigned an API-equivalent planning cost.

## Active role hierarchy

- Complex product logic, served UI, integration, browser-dependent work,
  sensitive work, and required live-tool work remain Codex-first.
- Bounded Pipeline execution starts with DeepSeek V4 Flash 0731 and escalates
  to Grok 4.6. Output still must pass the exact allowlist and unified-diff
  contract before native verification.
- Documentation and test-coverage review use DeepSeek Flash, then Luna.
- Pattern review uses DeepSeek Pro, then Qwen3.8 Max.
- Simplicity, ordinary independent review, and bulk analysis use Qwen3.8 Max,
  with DeepSeek Pro or Grok 4.6 according to the role's ordered list.
- Focused applicable security analysis alone uses Kimi K3, then Grok 4.6.
  Consequential security completion still requires a full-input reviewer from
  a family different from the implementer.

This hierarchy creates no provider quota. Applicability, disclosure,
availability, output validation, and family requirements still decide whether
a lane may run or must fall back to native Codex.

## dm-review and direct delegation topology

| Workload | OpenRouter primary | OpenRouter fallback |
|---|---|---|
| Direct `/openrouter` | `qwen/qwen3.8-max` | `x-ai/grok-4.6` |
| Pattern review | `deepseek/deepseek-v4-pro-0813` | `qwen/qwen3.8-max` |
| Simplicity review | `qwen/qwen3.8-max` | `deepseek/deepseek-v4-pro-0813` |
| Documentation review | `deepseek/deepseek-v4-flash-0731` | `openai/gpt-5.6-luna` |
| Test-coverage review | `deepseek/deepseek-v4-flash-0731` | `openai/gpt-5.6-luna` |
| Bulk analysis | `qwen/qwen3.8-max` | `deepseek/deepseek-v4-pro-0813` |
| Ordinary second perspective | `qwen/qwen3.8-max` | `x-ai/grok-4.6` |
| Focused security analysis | `moonshotai/kimi-k3` | `x-ai/grok-4.6` |

The fallback is part of one OpenRouter request when the wrapper is allowed to
use fallback. Native completion is a separate attempt with separate
provenance. Review timeouts remain 3600 seconds, or 7200 seconds for diffs of
at least 10,000 lines.

## Pipeline execution cascade

All supported hosts expose the same ordered OpenRouter models:

| Role | Ordered models |
|---|---|
| `openrouter_exec` | DeepSeek V4 Flash 0731 -> Grok 4.6 |
| `frontier_api` | Grok 4.6 -> Qwen3.8 Max -> DeepSeek V4 Pro 0813 |
| `cheap_api` | DeepSeek V4 Flash 0731 -> Qwen3.8 Max |
| `bulk_api` | Qwen3.8 Max -> DeepSeek V4 Pro 0813 -> Grok 4.6 |

The `codex` class walks native Codex before these OpenRouter roles; the
`openrouter` class may try the bounded executor first for eligible config,
documentation, or mechanical work. Wrapper roles never autonomously implement
complex logic, served UI, integration, browser-dependent, or live-tool work.

## Evidence interpretation

The 2026-08-17 canary supports DeepSeek Pro for the current unified-diff
contract, Qwen3.8 Max for concise independent review, and Grok 4.6 for demanding
review/escalation. DeepSeek Flash received an HTTP 429 before output; one
transport rate limit does not show that it cannot satisfy the output contract,
so it remains the cheap primary with no quality claim from that call. The
receipt records exact tokens, cost, timing, format, scope, and complexity.

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

Set `OPENROUTER_ALLOW_FALLBACKS=0` for a measured one-model call. Receipts must
record the requested and returned model so provider fallback is never confused
with model-family independence.
