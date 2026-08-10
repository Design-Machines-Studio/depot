# Migration: OpenRouter Leaf Plugin + Usage-Aware Executor Cascade

This note covers the `world-b-openrouter` changes: a shared `openrouter` provider plugin, a usage-aware model cascade wired into the pipeline executor handoff, and the removal of the Gemini and standalone DeepSeek plugins. Claude Code remains a compatible host, but Claude is outside the implementation graph.

**Temporary authority mode:** Pipeline implementation rungs and dm-review
review lanes have different authority contracts. Non-dry automated Pipeline
OpenRouter rungs remain unavailable until external broker integration; they
record `host_authority_unavailable` and descend to native Codex. dm-review may
use a validated absent-broker interim batch for eligible read-only review
lanes. Once a broker is ready, interim mode is retired and review remains
`broker_transport_unavailable` until broker-owned transport exists. Direct
interactive `/openrouter` remains exact-digest gated.

## What changed

1. **Unified leaf plugin `plugins/openrouter`** -- the sole external-provider primitive. It owns the wrapper, bulk analyst, and generic mechanical-agent runner; DeepSeek V4 remains a model choice through OpenRouter, not a separate plugin.
2. **Cascade in `execution-orchestrator.md` Step 3d** -- Codex and OpenRouter form the complete coding ladder (probe headroom -> on cap, Airlift checkpoint + descend). Legacy `executor: claude` manifests normalize to Codex.
3. **Claude has no implementation authority** -- it remains available for strategy, writing/voice, research synthesis, optional plan critique, and narrowly scoped read-only independent review when its family differs from the implementer. It never implements code, and it cannot satisfy an independent lane for a Claude-authored diff.
4. **Provider provenance is explicit** -- native Codex remains the preferred OpenAI coding rail, while receipted `openai/*` OpenRouter models are eligible for economical API work and capacity fallback. Anthropic models execute only through Claude-native non-coding/compatibility rails and `anthropic/*` remains forbidden on every OpenRouter primary and fallback.
5. **Installed assets resolve coherently** -- workflow-kernel `resolve-plugin-bundle` selects one highest compatible semantic-version root across Claude/Codex caches. Wrapper, boundary, policy, protocol, and template paths are derived from that root; assets are never combined by independent mtime lookup.

## Environment variables

| Variable | Where | Effect |
|----------|-------|--------|
| `OPENROUTER_API_KEY` | env / settings (never committed) | Required for direct interactive calls. It does not activate automated Pipeline or dm-review dispatch. |
| `PIPELINE_CASCADE=1` | env | Manual override that activates the cascade even without an API key (for testing the native-reroute and Airlift-on-cap paths). |
| `OPENROUTER_ZDR=1` | env (wrapper) | Opt-in privacy pin: restrict to providers that do not train on / retain data (`data_collection: deny`). Demoted by default (Quality > Price > Speed > Provider privacy); set only for genuinely sensitive material. |
| `OPENROUTER_SYSTEM` | env (wrapper) | System prompt. |
| `OPENROUTER_BASE` | env (wrapper) | API base URL (default `https://openrouter.ai/api/v1`). |
| `OPENROUTER_REQUIRE_PARAMS` | env (wrapper, default `1`) | Skip providers that do not support requested params. |
| `OPENROUTER_PROVIDER_SORT` | env (wrapper) | `throughput\|latency\|price` provider bias. |

`OPENROUTER_API_KEY` lives in environment or settings only -- `.env` and `*.local` are gitignored. Claude's main loop is never routed through OpenRouter (no `ANTHROPIC_BASE_URL`).

The generic host exposes no native OpenAI or Anthropic substitution. It may use explicitly configured OpenAI or third-party OpenRouter roles, while Anthropic intent remains unavailable rather than translated.

## Classes, kinds, and the ladder

The cascade keys off the merged chunk vocabulary. `model-cascade.json` maps `kind -> class`:

| kind | class | primary | on cap, descends to |
|------|-------|---------|---------------------|
| `logic`, `integration`, `ui` | `codex` | Codex subscription | GLM-5.2 OpenRouter exec -> quality-first OpenRouter wrapper ladder |
| `config`, `docs`, mechanical logic | `openrouter` | GLM-5.2 OpenRouter exec | Codex subscription -> quality-first OpenRouter wrapper ladder |

**Native Codex subscription capacity remains the first coding rail for logic, integration, and UI. GLM-5.2 is the Pipeline agentic OpenRouter execution head. Kimi K3 is the independent security and bulk-analysis head; Terra is its OpenRouter quality backup, while Luna is the economical dm-review mechanical rail.** The coding quality floor is 70. `harness-profile.json` is the only host-specific file (it resolves abstract roles to concrete rails per host).

## One-shot vs agentic (important)

`openrouter-wrapper.sh` is a **single-turn completion call**. It returns text; it cannot read/write files or run a tool loop.

- **Valid wrapper uses:** big-diff analysis, code review, second opinions, and config/doc text the orchestrator then writes to disk.
- **Invalid (wrapper):** autonomously implementing a code chunk with the *single-turn wrapper*. For `kind: ui|integration` and complex `logic`, a wrapper rung fast-fails and the orchestrator returns to an eligible agentic Codex/OpenRouter rung -- wrapper text is never piped in as an implementation.
- **Phase B (dormant pending broker):** the bounded executor and its offline
  regression suite exist, but production non-dry dispatch returns
  `host_authority_unavailable` before provider contact. Dry-run retains the
  planned `openrouter_exec` topology; native Codex performs current chunks.

## How to enable

Direct interactive use:

```bash
export OPENROUTER_API_KEY="sk-or-..."   # required for live wrapper calls; never authority by itself
# PIPELINE_CASCADE=1 may exercise dry-run/native reroute behavior; it cannot
# enable automated external transport.
```

## dm-review big-diff selection (>5000 lines)

```
valid absent-broker interim batch -> openrouter-bulk-analyst (Kimi K3 primary, Terra fallback)
ready broker without transport    -> unavailable (`broker_transport_unavailable`)
```

`OPENROUTER_API_KEY` is required for live wrapper transmission but does not
authorize automated review. dm-review may use a valid interim batch only while
the broker is absent; broker readiness alone remains unavailable until the
broker owns transport. The future broker-enabled and dry-run topology sends mechanical review criteria through
`openrouter-agent-runner`; policy selects each lane's primary and fallback.
Security retains separate `security-auditor-openrouter` eligible-content
analysis and mandatory `security-auditor-codex-signoff` full-diff completion;
the stable lane ID resolves to a family different from the implementer.

## Dry-run / verify (no API key needed)

```bash
D=plugins/pipeline/references/cascade-dispatch.sh
# default selection per kind
bash $D --dry-run --kind logic  --prompt x --host claude-code   # -> premium_sub codex
bash $D --dry-run --kind ui     --prompt x --host claude-code   # -> premium_sub codex
# mocked cap states drive the descent
echo '{"codex":{"state":"limited"},"openrouter":{"state":"ok"}}' > /tmp/p.json
bash $D --dry-run --kind logic --prompt x --host claude-code --probe-file /tmp/p.json  # -> openrouter_exec z-ai/glm-5.2
```

The wrapper exits 1 cleanly with no key; `usage-probe.sh` always emits valid JSON (openrouter `state: unknown` without creds).
