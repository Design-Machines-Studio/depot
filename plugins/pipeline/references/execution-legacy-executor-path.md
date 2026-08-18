# Legacy binary executor path

Loaded at Step 3d only when `CASCADE_ACTIVE=0` (no available cascade). Steps
3d.2 and 3d.4 may re-enter its native Codex path, but never its direct
OpenRouter path. A run with an active cascade never loads it.

> This block is the prior section 3d in full. It runs only when
> `CASCADE_ACTIVE=0` (no available cascade). Steps 3d.2 and 3d.4 may re-enter
> its native Codex path, but never its direct OpenRouter path.

**Executor routing:** Read the chunk's `executor` field from the manifest.

**When a legacy manifest says `executor: openrouter` while `CASCADE_ACTIVE=0`:**

1. Treat OpenRouter as unavailable and descend to Codex.
2. Do not call `$OPENROUTER_EXEC` directly from this legacy branch; configured-key dispatch belongs to the active cascade and remains bounded there.
3. If Codex is unavailable, fail the chunk.

**When `executor: codex` (or derived from `kind: logic` / `kind: config`):** Resolve Codex via dual-cache `$HOME/.claude/plugins/cache/openai-codex/codex` then `$HOME/.codex/plugins/cache/openai-codex/codex`. Invoke `node "${CODEX_ROOT}/scripts/codex-companion.mjs" task --write "<chunk prompt>"`. On success proceed to 3e. On failure, use OpenRouter only when the cascade selected an eligible agentic rung; otherwise fail. Never fall back to Claude for coding. Do not use `/codex:*`.
