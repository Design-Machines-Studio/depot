# Airlift checkpoints (dm-review)

Loaded only when the optional `airlift` plugin is installed. Airlift is an
OPTIONAL dependency: when it is absent, skip the checkpoint silently -- no
warning, coverage gap, or install request -- and never load this file.

Both checkpoints are tier-1 deterministic (pure local file + git work, no model
budget, no agent call, no network) and are skipped silently when airlift is
absent. On an early-warning trip (e.g. a budget threshold crossed mid-run),
flush immediately rather than waiting for the phase boundary. The caller names
which `--phase` to fire:

- **`dm-review-consolidation`** -- fire once the consolidated report exists so
  partially-complete findings survive a usage cap, rate limit, or model switch.
- **`dm-review-findings`** -- fire after the pending todo files are written on
  the default `todos/` text-file tracking path, so the `todos/*-pending-*.md`
  findings survive the same interruptions before `/dm-review-fix` runs.

```bash
CHECKPOINT_PHASE="${1:-dm-review-consolidation}"   # dm-review-consolidation | dm-review-findings
ENGINE=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ENGINE=$(ls -t "$CACHE"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)
  [ -n "$ENGINE" ] && break
done
if [ -n "$ENGINE" ] && [ -x "$ENGINE" ]; then bash "$ENGINE" write --phase "$CHECKPOINT_PHASE"; fi
```

The `[ -n "$ENGINE" ]` guard covers "airlift not installed"; `[ -x "$ENGINE" ]`
covers "resolved but not executable". Both guards sit within 3 lines of the
`airlift-engine.sh` invocation.
