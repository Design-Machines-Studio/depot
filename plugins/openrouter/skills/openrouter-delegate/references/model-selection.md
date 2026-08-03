# Model Selection

Decision table for choosing the right OpenRouter model for each delegation task. Native Codex subscription capacity remains the primary coding rail. On OpenRouter, Kimi K3 leads security and independent bulk analysis, Terra is the high-quality backup, and Luna is the economical mechanical workhorse.

## Available Models

Prices below are a checked-in planning snapshot from 2026-08-03, in USD per
million input/output tokens; they are not current telemetry. Before a paid or
policy-changing run, obtain a live MCP receipt with `observedAt` and `expiresAt`
no more than 15 minutes apart and use it only before expiry.

| Slug | Name | Input / output | Context | Quality and role |
|------|------|----------------|---------|------------------|
| `moonshotai/kimi-k3` | Kimi K3 | $3 / $15; $0.30 cache read | 1,048,576 | AA intelligence 57.1 / coding 76.2 / agentic 50.1; quality-first security and bulk-analysis head; reasoning efforts low/high/max |
| `openai/gpt-5.6-terra` | GPT-5.6 Terra | $1 / $6; $0.10 cache read | 1,050,000 | AA intelligence 55.0 / coding 76.7 / agentic 47.4; high-quality OpenRouter backup; reasoning none through max |
| `openai/gpt-5.6-luna` | GPT-5.6 Luna | $0.10 / $0.60; $0.01 cache read | 1,050,000 | AA intelligence 51.2 / coding 71.4 / agentic 45.6; low-cost mechanical and config/doc work; reasoning none through max |
| `x-ai/grok-4.5` | Grok 4.5 | $2 / $6 | 500K | AA 54; near-frontier value fallback |
| `z-ai/glm-5.2` | GLM-5.2 | catalog $1.19 / $3.74; lower-cost endpoints exist | 1M | AA intelligence 51.1 / coding 68.8 / agentic 43.1; third-party mechanical and security-capacity fallback |
| `meta/muse-spark-1.1` | Muse Spark 1.1 | $1.25 / $4.25 | 1M | AA 51; multimodal frontier value |
| `google/gemini-3.5-flash` | Gemini 3.5 Flash | $1.50 / $9 | 1M | AA 50; multimodal frontier tail |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | $0.435 / $0.87 | 1M | AA 44; cheap code-analysis fallback through OpenRouter |
| `minimax/minimax-m3` | MiniMax-M3 | $0.30 / $1.20 | 1M model; top endpoint about 524K | AA 44; multimodal cost workhorse |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash | $0.098 / $0.196 | 1M | AA 40; cheapest mechanical checks |
| `qwen/qwen3-coder` | Qwen3 Coder | $0.30 / $1 | 1M model; top endpoint about 262K | Lower-quality final bulk fallback; validate endpoint capacity before very large prompts |

## Task -> Model Mapping

| Task Type | Model | Timeout | Rationale |
|-----------|-------|---------|-----------|
| Agentic implementation | native Codex, then `openai/gpt-5.6-luna` / Terra on the OpenRouter fallback rail | 3600s | Spend flat-rate subscription capacity first; the API runner accepts only bounded unified diffs and leaves execution/verification authority with Codex. |
| Security analysis | `moonshotai/kimi-k3` | 3600s | Quality-first adversarial lens with enough completion time for large security payloads; independent Codex full-diff sign-off remains mandatory. |
| Big-diff review (<10K lines) | `moonshotai/kimi-k3` | 3600s | Independent high-quality lens; Terra covers provider capacity. |
| Big-diff review (>=10K lines) | `moonshotai/kimi-k3` | 7200s | 1M context; two-hour completion budget while first-byte and stream-idle watchdogs still detect dead transports. |
| Second-opinion analysis | `moonshotai/kimi-k3` | 3600s | Quality-first independent analysis. |
| Config / doc generation | `openai/gpt-5.6-luna` | 1800s | Low-cost one-shot text the caller writes to disk; Terra is the quality fallback. |
| Frontier cross-check (cascade) | `moonshotai/kimi-k3` | 3600s | Highest-quality eligible OpenRouter rung; native Codex is the fallback when valid OpenRouter capacity is exhausted. |

The current `openrouter-wrapper.sh` accepts text prompts only. Model modality columns describe upstream capability, not an operational claim that this rail can yet attach images, audio, video, or files.

## OpenRouter Fallback Chains

The wrapper accepts a `[fallback-slug]` (4th positional arg) and sends the
primary plus fallback as one ordered OpenRouter `models` array. OpenRouter can
therefore walk to the fallback for any eligible model error without the wrapper
issuing a second client request:

```
bulk:       moonshotai/kimi-k3 -> openai/gpt-5.6-terra -> z-ai/glm-5.2 -> minimax/minimax-m3 -> skip
mechanical: openai/gpt-5.6-luna -> deepseek/deepseek-v4-flash -> z-ai/glm-5.2 -> minimax/minimax-m3 -> skip
security:   moonshotai/kimi-k3 -> z-ai/glm-5.2 -> native Codex sign-off
direct:     openai/gpt-5.6-terra -> moonshotai/kimi-k3 -> skip
```

Native Codex remains ahead of these OpenRouter chains for subscription-primary
coding classes. OpenRouter's Terra and Luna conserve subscription headroom for
eligible mechanical work and provide paid fallback after a capacity event.
The wrapper accepts one native fallback; the pipeline cascade owns the full
ladder and continues through later models after the request is exhausted.

OpenAI slugs are allowed through the receipted OpenRouter rail. Anthropic slugs
remain invalid as a primary or fallback and use native Claude only for allowed
non-coding/compatibility lanes.

## Kimi Provider Routing

The 2026-07-28 OpenRouter MCP snapshot exposed seven Kimi endpoints across
BaseTen, DigitalOcean, Nebius, Fireworks, Together, Moonshot AI, and a premium
Fireworks-fast variant. Endpoint health changes independently from the model
catalog and benchmark datasets, so do not convert one telemetry snapshot into a
permanent availability claim.

Quality and security Kimi calls default to `provider.sort: "exacto"` through
`openrouter-wrapper.sh`. Direct, bulk, and mechanical workloads default to
`provider.sort: "throughput"` so long generations favor faster capacity while
retaining provider fallback. An explicit `OPENROUTER_PROVIDER_SORT` or provider
order overrides the workload default. For a reproducible eval or incident
replay, set an explicit endpoint order:

```bash
OPENROUTER_PROVIDER_ORDER=baseten/fp8,moonshotai/mxfp4 \
OPENROUTER_ALLOW_FALLBACKS=0 \
/openrouter --model moonshotai/kimi-k3 "<approved evaluation prompt>"
```

`baseten/fp8` and `moonshotai/mxfp4` were the strongest-uptime standard-price
routes in the inspected snapshot; they are examples, not timeless defaults.
Refresh `list-model-endpoints` and `list-providers` before changing a durable
order. `OPENROUTER_FALLBACK_PROVIDER_ORDER` appends fallback-model endpoints to
the same native request, preserving one deterministic ordered provider list.
The response model, serving provider, generation ID, and usage belong in
the call receipt so an alias such as `moonshotai/kimi-k3` remains reproducible
after its canonical dated slug advances.

## Privacy (demoted -- opt-in only)

Model selection priority is **Quality > Price > Speed > Provider privacy** (user directive, 2026-07-18). `OPENROUTER_ZDR=1` is **opt-in**, never a default: Chinese first-party hosting (Moonshot/DeepSeek/Z.AI) is acceptable by default. Set it per-call only for genuinely sensitive material (client code under NDA, credentials-adjacent diffs); it pins providers with `data_collection: deny`.

**Kimi K3 interaction:** Kimi is available through multiple OpenRouter
providers, but ZDR eligibility and endpoint data policy can change independently
from model availability. Re-check live endpoint policy before a sensitive run.
If `OPENROUTER_ZDR=1` leaves no eligible Kimi endpoint, the cascade walks to the
next model rung and records the fallback.

## Note on Roles vs Slugs

The pipeline cascade (`model-cascade.json` + `harness-profile.json`) references these same slugs by abstract role (`cheap_api`, `frontier_api`, `bulk_api`). `bulk_api` and `frontier_api` place Kimi first; `cheap_api` places Luna first. Keep this file's defaults aligned with those roles.
