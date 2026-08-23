# OpenRouter routing reference

Loaded only when an OpenRouter lane is eligible for this review. It carries the
standalone model/timeout fallback table used when `routing-policy.json` is
absent, and the automatic disclosure boundary that governs outbound bytes. A
review with no eligible OpenRouter lane never loads this file.

Routing decisions come from `plugins/pipeline/references/routing-policy.json`. **OpenRouter models + timeouts** (Phase 4 Branch A; `routing-policy.json` slugs override this standalone fallback table):

| Agent ID | Primary | Fallback | Timeout |
|---|---|---|---|
| `security-auditor-openrouter` | `moonshotai/kimi-k3` | `x-ai/grok-4.6` | 3600s |
| `pattern-recognition-specialist` | `deepseek/deepseek-v4-pro-0813` | `qwen/qwen3.8-max` | 1800s |
| `code-simplicity-reviewer` | `qwen/qwen3.8-max` | `deepseek/deepseek-v4-pro-0813` | 1800s |
| `doc-sync-reviewer` | `deepseek/deepseek-v4-flash-0731` | `openai/gpt-5.6-luna` | 1800s |
| `test-coverage-reviewer` | `deepseek/deepseek-v4-flash-0731` | `openai/gpt-5.6-luna` | 1800s |
| `openrouter-bulk-analyst` | `qwen/qwen3.8-max` | `deepseek/deepseek-v4-pro-0813` | 3600s; 7200s at ≥10K diff lines |

Print the routing report before Phase 4 (full mode prints it from `${CLAUDE_SKILL_DIR}/references/full-lane-dispatch.md` after availability resolves).

#### Automatic disclosure boundary

The configured key authorizes eligible development dispatch. Each runner partitions the immutable diff by complete file section, materializes the exact eligible system/user bytes, scans those private files once, and immediately invokes the wrapper. A credential/private-key match, authenticated DSN, access/session token, or explicitly classified private/regulated value keeps only that section local; safe sections still dispatch once and local coverage is restricted to held paths. Only an empty safe remainder or refused bytes in the exact outbound prompt causes a full decline. There is no approval prompt, broker probe, or sunset. The wrapper receipt records a request-envelope digest without prompt or response content.
