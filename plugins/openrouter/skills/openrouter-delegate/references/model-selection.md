# Model Selection

Decision table for choosing the right OpenRouter model for each delegation task. GLM-5.2 is the default quality-per-dollar pick; DeepSeek V4 is the alternate/fallback. Both carry 1M-token context.

## Available Models

Prices are the live OpenRouter catalog snapshot from 2026-07-18, in USD per million input/output tokens; re-check before long paid runs.

| Slug | Name | Input / output | Context | Quality and role |
|------|------|----------------|---------|------------------|
| `openai/gpt-5.6-sol` | GPT-5.6 Sol | $5 / $30 | 1.05M | AA 59; paid frontier head |
| `moonshotai/kimi-k3` | Kimi K3 | $3 / $15; $0.30 cache read | 1M | AA 57; quality-first OpenRouter agentic head, max-only reasoning; one capacity-limited provider |
| `anthropic/claude-opus-4.8` | Claude Opus 4.8 | $5 / $25 | 1M | AA 56; research/non-coding reference only, excluded from coding ladders |
| `openai/gpt-5.6-terra` | GPT-5.6 Terra | $2.50 / $15 | 1.05M | AA 55; precedes equally rated GPT-5.5 on price |
| `openai/gpt-5.5` | GPT-5.5 | $5 / $30 | 1.05M | AA 55; legacy/native-CLI fallback |
| `x-ai/grok-4.5` | Grok 4.5 | $2 / $6 | 500K | AA 54; near-frontier value fallback |
| `anthropic/claude-sonnet-5` | Claude Sonnet 5 | $2 / $10 | 1M | AA 53; research/non-coding reference only, excluded from coding ladders |
| `z-ai/glm-5.2` | GLM-5.2 | about $0.91 / $2.86 | 1M | AA 51; mechanical and bulk quality-per-dollar default |
| `meta/muse-spark-1.1` | Muse Spark 1.1 | $1.25 / $4.25 | 1M | AA 51; multimodal frontier value |
| `openai/gpt-5.6-luna` | GPT-5.6 Luna | $1 / $6 | 1.05M | AA 51; GLM wins the quality tie on price |
| `google/gemini-3.5-flash` | Gemini 3.5 Flash | $1.50 / $9 | 1M | AA 50; multimodal frontier tail |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | $0.435 / $0.87 | 1M | AA 44; cheap code-analysis fallback through OpenRouter |
| `minimax/minimax-m3` | MiniMax-M3 | $0.30 / $1.20 | 1M model; top endpoint about 524K | AA 44; multimodal cost workhorse |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash | $0.098 / $0.196 | 1M | AA 40; cheapest mechanical checks |
| `qwen/qwen3-coder` | Qwen3 Coder | $0.30 / $1 | 1M model; top endpoint about 262K | Lower-quality final bulk fallback; validate endpoint capacity before very large prompts |

## Task -> Model Mapping

| Task Type | Model | Timeout | Rationale |
|-----------|-------|---------|-----------|
| Agentic implementation | `moonshotai/kimi-k3` | 180s | Highest-quality OpenRouter agentic model in the Matrix; planned for open-weight release but API-only today. GLM-5.2 covers K3's current capacity constraint. |
| Big-diff review (<10K lines) | `z-ai/glm-5.2` | 120s | GLM-5.2 holds the full diff; mechanical quality-per-dollar default. |
| Big-diff review (>=10K lines) | `z-ai/glm-5.2` | 180s | 1M context; longer timeout for very large diffs. |
| Second-opinion analysis | `z-ai/glm-5.2` | 90s | Cheap cross-check that does not become the implementation. |
| Config / doc generation | `z-ai/glm-5.2` | 90s | One-shot text the caller writes to disk. |
| Frontier cross-check (cascade) | `openai/gpt-5.6-sol` | 120s | Paid frontier head; Kimi K3 is the next quality rung, then Terra and GPT-5.5. |

The current `openrouter-wrapper.sh` accepts text prompts only. Model modality columns describe upstream capability, not an operational claim that this rail can yet attach images, audio, video, or files.

## Rate-Limit Fallback Chain

The wrapper accepts a `[fallback-slug]` (4th positional arg). On HTTP 429/503 from the primary, it retries the fallback:

```
z-ai/glm-5.2 -> deepseek/deepseek-v4-pro -> minimax/minimax-m3 -> deepseek/deepseek-v4-flash -> qwen/qwen3-coder -> skip
```

For quality-first direct calls, pass `deepseek/deepseek-v4-pro` as the immediate fallback. Use `minimax/minimax-m3` instead only for an explicitly cost-first call. The wrapper accepts one fallback; the pipeline cascade owns the full ladder and continues through later models on per-model failures.

## Privacy (demoted -- opt-in only)

Model selection priority is **Quality > Price > Speed > Provider privacy** (user directive, 2026-07-18). `OPENROUTER_ZDR=1` is **opt-in**, never a default: Chinese first-party hosting (Moonshot/DeepSeek/Z.AI) is acceptable by default. Set it per-call only for genuinely sensitive material (client code under NDA, credentials-adjacent diffs); it pins providers with `data_collection: deny`.

**Kimi K3 interaction:** its sole OpenRouter provider is currently Moonshot's own first-party API, with no `data_collection: deny` variant. K3 is live under the default policy. Moonshot has announced a planned open-weight release, but hosting availability is not guaranteed; until OpenRouter exposes a ZDR-eligible K3 provider, `OPENROUTER_ZDR=1` makes K3 unavailable and the cascade walks to the next rung.

## Note on Roles vs Slugs

The pipeline cascade (`model-cascade.json` + `harness-profile.json`) references these same slugs by abstract role (`cheap_api`, `frontier_api`, `bulk_api`). The cheap_api ladder lists `z-ai/glm-5.2` first, so GLM-5.2 is always tried before DeepSeek V4 when a subscription rail caps. Keep this file's defaults aligned with that ordering.
