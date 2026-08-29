# Complete model-role eligibility grid

Source: Depot `origin/main` at `f0221f6a9e083385ea1114ffd8524b8a0626ad46`; OpenRouter catalog observed 2026-08-29T08:07:31+08:00.

Codes: **RI** routed incumbent; **CA** later routed canary; **CU** catalogued/admitted elsewhere but unrouted for this exact role; **SC** security-confined; **CI** capability-incompatible. A dagger marks a routed cell whose role had no sealed case.

| Exact candidate / transport | Architect | Plan critic | Builder fast | Builder deep | Review fast | Review deep | Security review | Research fast | Editorial |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek/deepseek-v4-flash-0731 / OpenRouter | CU | CU | RI | CU | RI | CU | CU | CU | CU |
| deepseek/deepseek-v4-pro-0813 / OpenRouter | CU | CA† | CU | CA† | CU | CA† | CU | CU | CU |
| qwen/qwen3.8-max / OpenRouter | CA | RI† | CU | CU | CU | RI† | CA† | CU | CA† |
| qwen/qwen3.8-2.4t-a95b / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| qwen/qwen3.8-27b / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| qwen/qwen3.7-flash / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| x-ai/grok-4.6 / OpenRouter | CU | CA† | CU | CA† | CU | CU | CA† | CU | CU |
| google/gemini-3.7-flash / OpenRouter | CU | CU | CU | CU | CU | CU | CU | RI† | CU |
| meta/muse-spark-1.2 / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| z-ai/glm-5.2 / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| moonshotai/kimi-k3 / OpenRouter | SC | SC | SC | SC | SC | SC | RI† | SC | SC |
| openai/gpt-5.6-luna / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| openai/gpt-5.6-terra / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| z-ai/glm-5.3 / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| z-ai/glm-5.3-flash / OpenRouter | CU | CU | CU | CU | CU | CU | CU | CU | CU |
| fable → claude-fable-5 / Claude CLI | RI | CU | CI | CI | CU | CU | CU | CU | RI† |
| opus / Claude CLI | CA | CA† | CI | CI | CU | CU | CA† | CU | CA† |
| gpt-5.6-sol / Codex CLI | CA | CU | CU | RI† | CU | CU | CU | CU | CU |
| gpt-5.6-terra / Codex CLI | CU | CA† | CU | CA† | CU | CA† | CA† | CU | CU |
| gpt-5.6-luna / Codex CLI | CI | CI | CA | CI | CA | CI | CI | CA† | CI |

Exact exclusion reasons:

- **CU:** the exact model/transport pair is absent from that role's ordered policy list.
- **SC:** Kimi K3 is confined to `security-review`; ordinary-role calls are prohibited.
- **CI:** the native candidate lacks a mandatory capability in checked policy evidence.
- **Insufficient context:** daggered cells lacked a sealed `depot-role-v1` case and were excluded without spend.
- **Family incompatibility:** invocation-specific; no opaque implementer-family receipt existed for this human-authored audit.
- **Unavailable after call:** the requested `opus` alias served `claude-haiku-4-5-20251001`, so the retained attempt is identity-unavailable evidence rather than Opus evidence.
