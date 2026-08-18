# Airlift checkpoint (dm-review consolidation)

Loaded only when the optional `airlift` plugin is installed. Airlift is an
OPTIONAL dependency: when it is absent, skip the checkpoint silently -- no
warning, coverage gap, or install request -- and never load this file.

**Airlift checkpoint (`dm-review-consolidation`):** Fire a tier-1 airlift checkpoint once the consolidated report exists so partially-complete findings survive a usage cap, rate limit, or model switch. Tier-1 deterministic (pure local file + git work, no model budget, no agent call, no network); skipped silently when airlift is absent (OPTIONAL dependency). On an early-warning trip, flush immediately rather than waiting for the phase boundary.

```bash
ENGINE=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ENGINE=$(ls -t "$CACHE"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)
  [ -n "$ENGINE" ] && break
done
if [ -n "$ENGINE" ] && [ -x "$ENGINE" ]; then bash "$ENGINE" write --phase dm-review-consolidation; fi
```

The `[ -n "$ENGINE" ]` guard covers "airlift not installed"; `[ -x "$ENGINE" ]` covers "resolved but not executable". Both guards sit within 3 lines of the `airlift-engine.sh` invocation.
