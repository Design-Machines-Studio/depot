# Model Selection

Decision table for choosing the right OpenRouter model for each delegation task. Kimi K3 is the quality-first default and security-analysis head; GLM-5.2 is its economical capacity fallback and remains first for lightweight mechanical checks.

## Available Models

Prices below are a checked-in planning snapshot from 2026-07-28, in USD per
million input/output tokens; they are not current telemetry. Before a paid or
policy-changing run, obtain a live MCP receipt with `observedAt` and `expiresAt`
no more than 15 minutes apart and use it only before expiry.

| Slug | Name | Input / output | Context | Quality and role |
|------|------|----------------|---------|------------------|
| `moonshotai/kimi-k3` | Kimi K3 | $3 / $15; $0.30 cache read | 1,048,576 | AA intelligence 57.1 / coding 76.2 / agentic 50.1; quality-first security and bulk-analysis head; reasoning efforts low/high/max |
| `x-ai/grok-4.5` | Grok 4.5 | $2 / $6 | 500K | AA 54; near-frontier value fallback |
| `z-ai/glm-5.2` | GLM-5.2 | about $0.91 / $2.86 | 1M | AA 51; lightweight mechanical default and Kimi capacity fallback |
| `meta/muse-spark-1.1` | Muse Spark 1.1 | $1.25 / $4.25 | 1M | AA 51; multimodal frontier value |
| `google/gemini-3.5-flash` | Gemini 3.5 Flash | $1.50 / $9 | 1M | AA 50; multimodal frontier tail |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | $0.435 / $0.87 | 1M | AA 44; cheap code-analysis fallback through OpenRouter |
| `minimax/minimax-m3` | MiniMax-M3 | $0.30 / $1.20 | 1M model; top endpoint about 524K | AA 44; multimodal cost workhorse |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash | $0.098 / $0.196 | 1M | AA 40; cheapest mechanical checks |
| `qwen/qwen3-coder` | Qwen3 Coder | $0.30 / $1 | 1M model; top endpoint about 262K | Lower-quality final bulk fallback; validate endpoint capacity before very large prompts |

## Task -> Model Mapping

| Task Type | Model | Timeout | Rationale |
|-----------|-------|---------|-----------|
| Agentic implementation | `moonshotai/kimi-k3` | 180s | Strong coding model and current open-weight release; this runner still accepts only bounded unified diffs and leaves execution/verification authority with Codex. |
| Security analysis | `moonshotai/kimi-k3` | 120s | Quality-first adversarial lens; completion still requires independent Codex full-diff sign-off. |
| Big-diff review (<10K lines) | `moonshotai/kimi-k3` | 120s | Highest-ranked eligible OpenRouter contender; GLM-5.2 covers provider capacity. |
| Big-diff review (>=10K lines) | `moonshotai/kimi-k3` | 180s | 1M context; longer timeout for very large diffs. |
| Second-opinion analysis | `moonshotai/kimi-k3` | 120s | Quality-first independent analysis. |
| Config / doc generation | `z-ai/glm-5.2` | 90s | One-shot text the caller writes to disk. |
| Frontier cross-check (cascade) | `moonshotai/kimi-k3` | 120s | Highest-quality eligible OpenRouter rung; native Codex is the fallback when valid OpenRouter capacity is exhausted. |

The current `openrouter-wrapper.sh` accepts text prompts only. Model modality columns describe upstream capability, not an operational claim that this rail can yet attach images, audio, video, or files.

## Rate-Limit Fallback Chain

The wrapper accepts a `[fallback-slug]` (4th positional arg). On HTTP 429/503 from the primary, it retries the fallback:

```
moonshotai/kimi-k3 -> z-ai/glm-5.2 -> deepseek/deepseek-v4-pro -> minimax/minimax-m3 -> deepseek/deepseek-v4-flash -> qwen/qwen3-coder -> skip
```

For quality-first direct calls, use Kimi K3 with `z-ai/glm-5.2` as the immediate fallback. Use GLM-5.2 first only for an explicitly economical mechanical call. The wrapper accepts one fallback; the pipeline cascade owns the full ladder and continues through later models on per-model failures.

OpenAI and Anthropic are deliberately absent from this catalog. Never pass `openai/*` or `anthropic/*` as a primary or fallback. OpenAI models use the native Codex CLI; Anthropic models use the native Claude CLI for the allowed non-coding/compatibility lanes.

## Kimi Provider Routing

The 2026-07-28 OpenRouter MCP snapshot exposed seven Kimi endpoints across
BaseTen, DigitalOcean, Nebius, Fireworks, Together, Moonshot AI, and a premium
Fireworks-fast variant. Endpoint health changes independently from the model
catalog and benchmark datasets, so do not convert one telemetry snapshot into a
permanent availability claim.

Routine Kimi calls default to `provider.sort: "exacto"` through
`openrouter-wrapper.sh`. Exacto lets OpenRouter continuously apply its
quality-first provider signals while retaining fallback capacity. For a
reproducible eval or incident replay, set an explicit endpoint order:

```bash
OPENROUTER_PROVIDER_ORDER=baseten/fp8,moonshotai/mxfp4 \
OPENROUTER_ALLOW_FALLBACKS=0 \
/openrouter --model moonshotai/kimi-k3 "<approved evaluation prompt>"
```

`baseten/fp8` and `moonshotai/mxfp4` were the strongest-uptime standard-price
routes in the inspected snapshot; they are examples, not timeless defaults.
Refresh `list-model-endpoints` and `list-providers` before changing a durable
order. A primary-specific order is not reused for a different fallback model;
set `OPENROUTER_FALLBACK_PROVIDER_ORDER` when a reproducible fallback endpoint
order is also required.
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

The pipeline cascade (`model-cascade.json` + `harness-profile.json`) references these same slugs by abstract role (`cheap_api`, `frontier_api`, `bulk_api`). `bulk_api` and `frontier_api` place Kimi first; `cheap_api` keeps GLM-5.2 first but includes Kimi before DeepSeek. Keep this file's defaults aligned with those roles.
