# Model Selection

Decision table for choosing the right OpenRouter model for each delegation task. GLM-5.2 is the default quality-per-dollar pick; DeepSeek V4 is the alternate/fallback. Both carry 1M-token context.

## Available Models

| Slug | Name | Strengths | Context | Role |
|------|------|-----------|---------|------|
| `z-ai/glm-5.2` | GLM-5.2 | Strong code reasoning at low cost. The preferred quality-per-dollar fallback when a subscription rail caps. | 1M | **Default** |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | Sonnet-class code reasoning. | 1M | Alternate / fallback |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash | Fast, cheap, mechanical checks. | 1M | Bulk / cheap |
| `minimax/minimax-m3` | MiniMax-M3 | Cost-optimized B-tier workhorse -- the cost-per-action pick for high-volume/bulk work; slightly under GLM-5.2 on quality. | large | Cost / bulk |
| `openai/gpt-5.6-sol` | GPT-5.6 Sol | Preferred frontier cross-check (leads the `frontier_api` rung). Same $5/$30 and 1.05M context as GPT-5.5, newer generation. | 1.05M | **Frontier** |
| `openai/gpt-5.5` | GPT-5.5 | Frontier fallback, one rung under Sol. | 1.05M | Frontier |
| `anthropic/claude-opus-4.8` | Claude Opus 4.8 | Frontier alternate. Used only on the cascade's `frontier_api` rung (never the main loop). | 1M | Frontier |
| `openai/gpt-5.6-terra` | GPT-5.6 Terra | Mid frontier rung ($2.50/$15). OpenAI's recommended production default; sits between Opus 4.8 and Sonnet 5. | 1.05M | Frontier (mid) |
| `openai/gpt-5.6-luna` | GPT-5.6 Luna | Frontier TAIL, not a cheap rung. At $1/$6 it is the cheapest OpenAI model but its output costs 3.4x GLM-5.2 and 6.9x DeepSeek V4 Pro -- never put it above `z-ai/glm-5.2` on `cheap_api`. | 1.05M | Frontier (tail) |

## Task -> Model Mapping

| Task Type | Model | Timeout | Rationale |
|-----------|-------|---------|-----------|
| Big-diff review (<10K lines) | `z-ai/glm-5.2` | 120s | GLM-5.2 holds the full diff; quality-per-dollar default. |
| Big-diff review (>=10K lines) | `z-ai/glm-5.2` | 180s | 1M context; longer timeout for very large diffs. |
| Second-opinion analysis | `z-ai/glm-5.2` | 90s | Cheap cross-check that does not become the implementation. |
| Config / doc generation | `z-ai/glm-5.2` | 90s | One-shot text the caller writes to disk. |
| Frontier cross-check (cascade) | `openai/gpt-5.6-sol` | 120s | Only on the `frontier_api` rung when a primary rail caps. Falls back to `openai/gpt-5.5`. |

## Rate-Limit Fallback Chain

The wrapper accepts a `[fallback-slug]` (4th positional arg). On HTTP 429/503 from the primary, it retries the fallback:

```
z-ai/glm-5.2 -> minimax/minimax-m3 -> deepseek/deepseek-v4-pro -> deepseek/deepseek-v4-flash -> qwen/qwen3-coder -> skip
```

For direct wrapper calls, pass `minimax/minimax-m3` as the immediate fallback when cost-per-action matters, or `deepseek/deepseek-v4-pro` when quality is more important than price. The pipeline cascade owns the full ladder and will continue walking through later models on per-model failures.

## Privacy

For any review of private code, set `OPENROUTER_ZDR=1` so the wrapper pins providers that do not train on or retain data (`data_collection: deny`). The cascade's cheap/frontier wrapper rungs set this by default.

## Note on Roles vs Slugs

The pipeline cascade (`model-cascade.json` + `harness-profile.json`) references these same slugs by abstract role (`cheap_api`, `frontier_api`, `bulk_api`). The cheap_api ladder lists `z-ai/glm-5.2` first, so GLM-5.2 is always tried before DeepSeek V4 when a subscription rail caps. Keep this file's defaults aligned with that ordering.
