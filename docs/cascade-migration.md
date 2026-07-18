# Migration: OpenRouter Leaf Plugin + Usage-Aware Executor Cascade

This note covers the `world-b-openrouter` changes: a shared `openrouter` provider plugin, a usage-aware model cascade wired into the pipeline executor handoff, and the removal of the Gemini and standalone DeepSeek plugins. Claude Code remains a compatible host, but Claude is now outside the executable coding graph.

## What changed

1. **Unified leaf plugin `plugins/openrouter`** -- the sole external-provider primitive. It owns the wrapper, bulk analyst, and generic mechanical-agent runner; DeepSeek V4 remains a model choice through OpenRouter, not a separate plugin.
2. **Cascade in `execution-orchestrator.md` Step 3d** -- Codex and OpenRouter form the complete coding ladder (probe headroom -> on cap, Airlift checkpoint + descend). Legacy `executor: claude` manifests normalize to Codex.
3. **Claude is non-coding-only** -- it remains available for strategy, writing/voice, research synthesis, and optional plan critique, but never for implementation or code review.

## Environment variables

| Variable | Where | Effect |
|----------|-------|--------|
| `OPENROUTER_API_KEY` | env / settings (never committed) | Opt-in signal. Required for any wrapper call. Its presence activates the pipeline cascade and makes `openrouter-bulk-analyst` the preferred dm-review big-diff analyst. |
| `PIPELINE_CASCADE=1` | env | Manual override that activates the cascade even without an API key (for testing the native-reroute and Airlift-on-cap paths). |
| `OPENROUTER_ZDR=1` | env (wrapper) | Opt-in privacy pin: restrict to providers that do not train on / retain data (`data_collection: deny`). Demoted by default (Quality > Price > Speed > Provider privacy); set only for genuinely sensitive material. |
| `OPENROUTER_SYSTEM` | env (wrapper) | System prompt. |
| `OPENROUTER_BASE` | env (wrapper) | API base URL (default `https://openrouter.ai/api/v1`). |
| `OPENROUTER_REQUIRE_PARAMS` | env (wrapper, default `1`) | Skip providers that do not support requested params. |
| `OPENROUTER_PROVIDER_SORT` | env (wrapper) | `throughput\|latency\|price` provider bias. |

`OPENROUTER_API_KEY` lives in environment or settings only -- `.env` and `*.local` are gitignored. Claude's main loop is never routed through OpenRouter (no `ANTHROPIC_BASE_URL`).

## Classes, kinds, and the ladder

The cascade keys off the merged chunk vocabulary. `model-cascade.json` maps `kind -> class`:

| kind | class | primary | on cap, descends to |
|------|-------|---------|---------------------|
| `logic`, `integration`, `ui` | `codex` | Codex subscription | Kimi K3 OpenRouter exec -> quality-first OpenRouter ladder |
| `config`, `docs`, mechanical logic | `openrouter` | Kimi K3 OpenRouter exec | quality-first OpenRouter ladder -> Codex subscription |

**Kimi K3 is the quality-first OpenRouter execution head; GLM-5.2 (`z-ai/glm-5.2`, 1M ctx) remains the preferred mechanical and bulk quality-per-dollar model.** The coding quality floor is 70. `harness-profile.json` is the only host-specific file (it resolves abstract roles to concrete rails per host).

## One-shot vs agentic (important)

`openrouter-wrapper.sh` is a **single-turn completion call**. It returns text; it cannot read/write files or run a tool loop.

- **Valid wrapper uses:** big-diff analysis, code review, second opinions, and config/doc text the orchestrator then writes to disk.
- **Invalid (wrapper):** autonomously implementing a code chunk with the *single-turn wrapper*. For `kind: ui|integration` and complex `logic`, a wrapper rung fast-fails and the orchestrator returns to an eligible agentic Codex/OpenRouter rung -- wrapper text is never piped in as an implementation.
- **Phase B (built):** the agentic OpenRouter executor now exists as `plugins/pipeline/references/openrouter-exec.sh`, dispatched via the `openrouter_exec` rung in `cascade-dispatch.sh` / `harness-profile.json`. It asks OpenRouter for a unified diff, applies it, runs the verify command, commits, and emits the `implementedBy: openrouter` receipt shape. It is the primary rung for `config`/`docs`/mechanical-`logic` chunks; the single-turn wrapper remains for analysis and text-generation only.

## How to enable

Default (no env) = current behavior, unchanged. To opt in:

```bash
export OPENROUTER_API_KEY="sk-or-..."   # activates the cascade + dm-review external routing
# optional: export PIPELINE_CASCADE=1   # force cascade path without a key (testing)
```

## dm-review big-diff selection (>5000 lines)

```
OPENROUTER_API_KEY set        -> openrouter-bulk-analyst (GLM-5.2, preferred)
neither                       -> Codex-native review
```

Mechanical-agent routing (pattern-recognition, code-simplicity, doc-sync, test-coverage) uses `openrouter-agent-runner`, with GLM-5.2 primary and DeepSeek V4 Pro as an OpenRouter model fallback.

## Dry-run / verify (no API key needed)

```bash
D=plugins/pipeline/references/cascade-dispatch.sh
# default selection per kind
bash $D --dry-run --kind logic  --prompt x --host claude-code   # -> premium_sub codex
bash $D --dry-run --kind ui     --prompt x --host claude-code   # -> premium_sub codex
# mocked cap states drive the descent
echo '{"codex":{"state":"limited"},"openrouter":{"state":"ok"}}' > /tmp/p.json
bash $D --dry-run --kind logic --prompt x --host claude-code --probe-file /tmp/p.json  # -> openrouter_exec moonshotai/kimi-k3
```

The wrapper exits 1 cleanly with no key; `usage-probe.sh` always emits valid JSON (openrouter `state: unknown` without creds).
