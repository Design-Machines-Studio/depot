# Case-coverage grid

Fresh run only. `P/S` means perfect retained attempts / scheduled attempts. A perfect attempt parsed, scored 100/100, used no model fallback, and retained actual served identity.

| Exact candidate / transport | pipeline-legacy-translation | mechanical-owned-edit | review-zero-deferral | assembly-next-chunk |
|---|---|---|---|---|
| DeepSeek V4 Flash / OpenRouter | 3/3, 100 | 3/3, 100 | 3/3, 100 | excluded: CU |
| Qwen3.8 Max / OpenRouter | excluded: CU | excluded: CU | excluded: CU | 0/1, 15 |
| Fable / Claude CLI | excluded: CI | excluded: CI | excluded: CU | 0/1, parse failure |
| Opus request / Claude CLI | excluded: CI | excluded: CI | excluded: CU | 0/1, Haiku served |
| GPT-5.6 Sol / Codex CLI | excluded: CU | excluded: CU | excluded: CU | 0/1, 30 |
| GPT-5.6 Luna / Codex CLI | 1/1, 100 | 0/1, 50 | 3/3, 100 | excluded: CI |

All other OpenRouter matrix candidates were excluded from these exact role cells by policy or security confinement.

| Role | Sealed cases | Routed cells screened | Complete three-attempt candidates | Gap |
|---|---:|---:|---|---|
| architect | 1 | 4/4 | 0 | no proven candidate |
| builder-fast | 2 | 2/2 | DeepSeek Flash only | single viable model/family |
| review-fast | 1 | 2/2 | DeepSeek Flash; native Luna | no production canary attribution |
| plan-critic | 0 | 0/5 | 0 | insufficient context |
| builder-deep | 0 | 0/4 | 0 | insufficient context |
| review-deep | 0 | 0/3 | 0 | insufficient context |
| security-review | 0 | 0/5 | 0 | insufficient context |
| research-fast | 0 | 0/2 | 0 | insufficient context |
| editorial | 0 | 0/3 | 0 | insufficient context |
