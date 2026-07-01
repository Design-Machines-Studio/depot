# Migration: OpenRouter Leaf Plugin + Usage-Aware Executor Cascade

This note covers the `world-b-openrouter` changes: a shared `openrouter` provider plugin, a usage-aware model cascade wired into the pipeline executor handoff, and the full removal of the Gemini plugin. **The cascade is backward-compatible: with no new environment variables set, executor behavior is byte-for-byte identical to before.**

## What changed

1. **New leaf plugin `plugins/openrouter`** -- a provider primitive (no internal dependencies) that both pipeline and dm-review `optionalPluginDependencies` on. Owns `openrouter-wrapper.sh` (canonical home) and the `openrouter-bulk-analyst` review agent. Mirrors the `deepseek` provider-plugin shape.
2. **Cascade in `execution-orchestrator.md` Step 3d** -- the binary "Codex unavailable -> Claude" fallback is generalized into a usage-aware ladder (probe headroom -> on cap, Airlift checkpoint + descend). The prior block is preserved verbatim as **3d-LEGACY** and runs unchanged when the cascade is inactive.
3. **Gemini removed entirely** -- from pipeline (research Agent 6 -> Claude-native WebSearch/WebFetch), dm-review (big-diff fallback -> `openrouter-bulk-analyst`), and airlift (dropped as a resume target). The `plugins/gemini` plugin is deleted.

## Environment variables

| Variable | Where | Effect |
|----------|-------|--------|
| `OPENROUTER_API_KEY` | env / settings (never committed) | Opt-in signal. Required for any wrapper call. Its presence activates the pipeline cascade and makes `openrouter-bulk-analyst` the preferred dm-review big-diff analyst. |
| `PIPELINE_CASCADE=1` | env | Manual override that activates the cascade even without an API key (for testing the native-reroute and Airlift-on-cap paths). |
| `OPENROUTER_ZDR=1` | env (wrapper) | Privacy pin: restrict to providers that do not train on / retain data (`data_collection: deny`). Set by the bulk analyst and recommended for any private-code review. |
| `OPENROUTER_SYSTEM` | env (wrapper) | System prompt. |
| `OPENROUTER_BASE` | env (wrapper) | API base URL (default `https://openrouter.ai/api/v1`). |
| `OPENROUTER_REQUIRE_PARAMS` | env (wrapper, default `1`) | Skip providers that do not support requested params. |
| `OPENROUTER_PROVIDER_SORT` | env (wrapper) | `throughput\|latency\|price` provider bias. |

`OPENROUTER_API_KEY` lives in environment or settings only -- `.env` and `*.local` are gitignored. Claude's main loop is never routed through OpenRouter (no `ANTHROPIC_BASE_URL`).

## Classes, kinds, and the ladder

The cascade keys off the merged chunk vocabulary. `model-cascade.json` maps `kind -> class`:

| kind | class | primary | on cap, descends to |
|------|-------|---------|---------------------|
| `logic`, `config` | `codex` | Codex (codex-companion) | GLM-5.2 (cheap_api) -> Claude native |
| `ui`, `integration` | `claude` | Claude native | frontier_api (Opus 4.8 / GPT-5.5) |

**GLM-5.2 (`z-ai/glm-5.2`, 1M ctx) is the preferred quality-per-dollar fallback** -- it is first in the `cheap_api` ladder and the default for `openrouter-bulk-analyst`. Quality floors: codex 70, claude 80. `harness-profile.json` is the only host-specific file (it resolves abstract roles to concrete rails per host).

## One-shot vs agentic (important)

`openrouter-wrapper.sh` is a **single-turn completion call**. It returns text; it cannot read/write files or run a tool loop.

- **Valid wrapper uses:** big-diff analysis, code review, second opinions, and config/doc text the orchestrator then writes to disk.
- **Invalid (wrapper):** autonomously implementing a code chunk with the *single-turn wrapper*. For `kind: ui|integration` and complex `logic`, a wrapper rung **fast-fails and the orchestrator descends Codex -> Claude** -- wrapper text is never piped in as an implementation.
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
only DEEPSEEK_API_KEY set     -> deepseek-bulk-analyst
neither                       -> truncated-diff Claude review (unchanged)
```

DeepSeek mechanical-agent routing (pattern-recognition, code-simplicity, doc-sync, test-coverage) is unchanged.

## Dry-run / verify (no API key needed)

```bash
D=plugins/pipeline/references/cascade-dispatch.sh
# default selection per kind
bash $D --dry-run --kind logic  --prompt x --host claude-code   # -> premium_sub codex
bash $D --dry-run --kind ui     --prompt x --host claude-code   # -> native_judgment opus
# mocked cap states drive the descent
echo '{"codex":{"state":"limited"},"claude":{"state":"ok"},"openrouter":{"state":"ok"}}' > /tmp/p.json
bash $D --dry-run --kind logic --prompt x --host claude-code --probe-file /tmp/p.json  # -> cheap_api z-ai/glm-5.2
```

The wrapper exits 1 cleanly with no key; `usage-probe.sh` always emits valid JSON (openrouter `state: unknown` without creds).
