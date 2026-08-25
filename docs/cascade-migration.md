# Historical Migration: OpenRouter Leaf Plugin + Executor Cascade

This note records the retired `world-b-openrouter` cascade. Current execution
uses provider-neutral role requests through model-router;
`cascade-dispatch.sh` remains only as a legacy CLI adapter. Claude Code remains
a compatible host, but Claude is outside the implementation graph.

The adapter preserves inline/stdin prompts and stdout output. It is read-only
unless a caller supplies an authoritative `--contract-digest` and
`--contract-revision`; it never fabricates behavioral-contract provenance.

**Configured-key mode:** a coherent installed bundle plus either supported key
input makes direct, dm-review, and bounded Pipeline lanes available with the
same input eligibility as native Claude/Codex candidates. Missing/invalid
credentials or provider unavailability descends to native Codex without a
prompt; payload content does not. The configured-key path has no broker dependency.

## What changed

1. **Unified leaf plugin `plugins/openrouter`** -- the sole external-provider primitive. It owns the wrapper, bulk analyst, and generic mechanical-agent runner; DeepSeek V4 remains a model choice through OpenRouter, not a separate plugin.
2. **Cascade in `execution-orchestrator.md` Step 3d** -- Codex and OpenRouter form the complete coding ladder (probe headroom -> on cap, Airlift checkpoint + descend). Legacy `executor: claude` manifests normalize to Codex.
3. **Claude has no implementation authority** -- it remains available for strategy, writing/voice, research synthesis, optional plan critique, and narrowly scoped read-only independent review when its family differs from the implementer. It never implements code, and it cannot satisfy an independent lane for a Claude-authored diff.
4. **Provider provenance is explicit** -- native Codex remains the preferred OpenAI coding rail, while receipted `openai/*` OpenRouter models are eligible for economical API work and capacity fallback. Anthropic models execute only through Claude-native non-coding/compatibility rails and `anthropic/*` remains forbidden on every OpenRouter primary and fallback.
5. **Installed assets resolve coherently** -- workflow-kernel `resolve-plugin-bundle` selects one highest compatible semantic-version root across Claude/Codex caches. Wrapper, boundary, policy, protocol, and template paths are derived from that root; assets are never combined by independent mtime lookup.

## Environment variables

| Variable | Where | Effect |
|----------|-------|--------|
| `OPENROUTER_API_KEY` | env / settings (never committed) | Enables eligible configured-key direct, dm-review, and bounded Pipeline dispatch. |
| `OPENROUTER_API_KEY_FILE` | env / settings (never committed) | Same authorization after the wrapper's ownership/mode/symlink validation. |
| `OPENROUTER_ZDR=1` | env (wrapper) | Opt-in privacy pin: restrict to providers that do not train on / retain data (`data_collection: deny`). Demoted by default (Quality > Price > Speed > Provider privacy); set only for genuinely sensitive material. |
| `OPENROUTER_SYSTEM` | env (wrapper) | System prompt. |
| `OPENROUTER_BASE` | env (wrapper) | API base URL (default `https://openrouter.ai/api/v1`). |
| `OPENROUTER_REQUIRE_PARAMS` | env (wrapper, default `1`) | Skip providers that do not support requested params. |
| `OPENROUTER_PROVIDER_SORT` | env (wrapper) | `throughput\|latency\|price` provider bias. |

`OPENROUTER_API_KEY` lives in environment or settings only -- `.env` and `*.local` are gitignored. Claude's main loop is never routed through OpenRouter (no `ANTHROPIC_BASE_URL`).

The generic host exposes no native OpenAI or Anthropic substitution. It may use explicitly configured OpenAI or third-party OpenRouter roles, while Anthropic intent remains unavailable rather than translated.

## Historical classes and kinds

The retired cascade mapped chunk kinds to classes as follows. Current manifests
carry `executorRole`, `executorCapabilities`, and `executorEffort`; concrete
candidates live only in model-router's private policy.

| kind | class | primary | on cap, descends to |
|------|-------|---------|---------------------|
| `logic`, `integration`, `ui` | `codex` | Codex subscription | eligible OpenRouter roles only after native capacity descent |
| `config`, `docs`, mechanical logic | `openrouter` | DeepSeek V4 Flash 0731 OpenRouter exec | Grok 4.6 -> Codex subscription -> wrapper ladder |

These model assignments are historical context, not current routing
instructions. Consult model-router's policy and content-free private receipts
for current candidate order and the served attempt.

## One-shot vs agentic (important)

`openrouter-wrapper.sh` is a **single-turn completion call**. It returns text; it cannot read/write files or run a tool loop.

- **Valid wrapper uses:** big-diff analysis, code review, second opinions, and config/doc text the orchestrator then writes to disk.
- **Invalid (wrapper):** autonomously implementing a code chunk with the *single-turn wrapper*. For `kind: ui|integration` and complex `logic`, a wrapper rung fast-fails and the orchestrator returns to an eligible agentic Codex/OpenRouter rung -- wrapper text is never piped in as an implementation.
- **Phase B (active bounded lane):** the configured-key executor requires
  `OPENROUTER_EXEC_ALLOWED_PATHS`, accepts only a validated unified diff within
  that allowlist, and defers correctness verification to native Codex.

## How to enable

Direct interactive use:

```bash
export OPENROUTER_API_KEY="sk-or-..."   # required for live configured-key calls
# Set a provider-side per-key spending limit for runaway-cost control.
```

## dm-review big-diff selection (>5000 lines)

```
configured key                     -> openrouter-bulk-analyst (Qwen3.8 Max primary, DeepSeek V4 Pro 0813 fallback)
missing/invalid key                -> native Codex
```

Either supported key input authorizes live review under the same input rules as
native candidates; OpenRouter adds no content, secret-value, or disclosure
eligibility gate. The active topology sends provider-neutral role requests
through model-router. The stable security lane requires an independent family
and complete repository evidence; a supplementary bulk lane cannot replace it.

## Verify the current router (no API key needed)

```bash
./tools/test-model-router.sh
./tools/validate-provider-neutral-routing.sh
```

`availability-probe.sh` emits the current subscription and configured-key
availability shape. Missing credentials remain `unknown` and fail closed.
