# Model Selection

Decision table for choosing the right DeepSeek V4 model for each delegation task.

## Available Models

| Model | Alias | Parameters | Strengths | Latency | Cost (Input/Output per MTok) |
|-------|-------|------------|-----------|---------|------------------------------|
| `deepseek-v4-pro` | `v4-pro` | 1.6T total, 49B active | Near-Opus SWE-bench (80.6%). Deep code reasoning. 1M context. | 5-60s | $1.74 / $3.48 |
| `deepseek-v4-flash` | `v4-flash` | 284B total, 13B active | Fast, cheap. Good for mechanical checks and extraction. 1M context. | 1-10s | $0.14 / $0.28 |

## Task -> Model Mapping

| Task Type | Model | Timeout | Rationale |
|-----------|-------|---------|-----------|
| Code review (quality, patterns) | `v4-pro` | 60s | Matches Opus 4.6 on coding benchmarks; best quality for review |
| Diff analysis (<10K lines) | `v4-flash` | 60s | Fast enough for medium diffs with decent analysis quality |
| Diff analysis (>10K lines) | `v4-pro` | 180s | Larger diffs benefit from deeper reasoning |
| Anti-pattern scan | `v4-flash` | 15s | Mechanical pattern matching, no deep reasoning needed |
| Doc-sync verification | `v4-flash` | 15s | Cross-reference check, pattern matching |
| Refactoring suggestions | `v4-pro` | 60s | Benefits from understanding intent, not just structure |
| Architecture analysis | `v4-pro` | 120s | Complex reasoning about system design |
| Simple text extraction | `v4-flash` | 10s | No reasoning needed, just extraction |
| Plan feasibility checks | `v4-pro` | 60s | File existence and API verification needs code understanding |

## Rate Limit Fallback Chain

When a model hits rate limits (HTTP 429), fall back:

```
v4-pro -> v4-flash -> skip
```

**Important:** Do not retry the same model. The wrapper handles the chain automatically.

## When V4-Pro Is Worth the Wait

Use V4-Pro when:
1. The task involves code quality judgment (not just pattern matching)
2. Cross-file analysis matters (architectural review, dependency tracing)
3. The output feeds into a decision gate (adversary feasibility check)

For everything else, V4-Flash provides adequate quality at 8% of V4-Pro's cost.

## Comparison with Anthropic Models

| Benchmark | Opus 4.6 | V4-Pro | V4-Flash | Sonnet 4.6 |
|-----------|----------|--------|----------|------------|
| SWE-bench Verified | 80.8% | 80.6% | ~65% | ~72% |
| Terminal-Bench 2.0 | 65.4% | 67.9% | ~48% | ~55% |
| LiveCodeBench | 88.8% | 93.5% | ~72% | ~78% |

V4-Pro is Sonnet-replacement tier for code work. V4-Flash is Haiku-replacement tier.
