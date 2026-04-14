# Model Selection

Decision table for choosing the right Gemini model for each delegation task.

## Available Models

| Model | Alias | Strengths | Latency | Cost |
|-------|-------|-----------|---------|------|
| `gemini-2.5-flash` | `flash` | Balanced speed and quality. Auto-uses search grounding, code execution. Good for most tasks. | 2-45s | Low |
| `gemini-2.5-pro` | `pro` | Deep reasoning. Best for large, complex analysis. Highest quality output. | 60-180s | High |
| `gemini-2.5-flash-lite` | `flash-lite` | Fastest possible response. Good for simple extraction, factual lookup. | 1-3s | Very low |

## Task → Model Mapping

| Task Type | Model | Timeout | Rationale |
|-----------|-------|---------|-----------|
| Quick factual lookup | `flash-lite` | 10s | Fastest response for simple questions |
| Web search with citations | `flash` | 60s | Search grounding works on all models; flash is the best cost/quality tradeoff |
| Diff analysis (<10K lines) | `flash` | 60s | Fast enough for medium diffs with good analysis quality |
| Diff analysis (>10K lines) | `pro` | 300s | Larger diffs need deeper reasoning; Pro retries internally with backoff |
| Code execution verification | `flash` | 30s | Python sandbox is model-independent; flash is cheaper |
| Deep architectural analysis | `pro` | 300s | Complex reasoning about system design benefits from Pro |
| Full-repo architectural scan | `pro` | 300s | Cross-file dependency analysis across entire codebase |
| Simple text extraction | `flash-lite` | 10s | No reasoning needed, just extraction |
| Summarization | `flash` | 30s | Good balance of quality and speed |
| Research synthesis | `flash` | 60s | May trigger search grounding; needs decent reasoning |

## Rate Limit Fallback Chain

When a model hits quota limits (`RetryableQuotaError`), fall back through:

```
pro → flash → flash-lite → skip
```

**Important:** Do not retry the same model. Gemini CLI already retries internally (up to 10 attempts with exponential backoff). If the CLI returns a quota error, the capacity is genuinely exhausted for that model.

## Model Selection in Practice

When invoking Gemini, always use the alias (not the full model ID):

```bash
# Good — uses alias
gemini -p "..." -m flash --output-format json --raw-output

# Avoid — full model IDs change between versions
gemini -p "..." -m gemini-2.5-flash --output-format json --raw-output
```

Gemini CLI resolves aliases to the current production model internally.

## When Pro Is Worth the Wait

Use Pro only when:
1. The input is very large (>10K lines) AND cross-file analysis matters
2. The task requires multi-step reasoning (architectural review, root cause analysis)
3. The output quality justifies the 60-180s latency

For everything else, Flash provides 80% of Pro's quality at 10% of the latency.
