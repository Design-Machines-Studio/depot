# Airlift Checkpoint Contract

The pipeline fires a tier-1 airlift checkpoint at every phase boundary and after every sub-agent / worktree completes. A checkpoint is a deterministic snapshot of the working session into a portable `.airlift/` bundle so a usage cap, rate limit, or model switch becomes a non-event -- the next session resumes from objective state instead of from a dying model's notes.

Airlift is an OPTIONAL dependency. Every checkpoint call is a guarded resolve-from-cache and is a silent no-op when airlift is absent.

## What gets captured

The checkpoint records only state the orchestrator already has -- no new analysis, no model reasoning:

- The plan (`plans/<feature-slug>/plan.html` and the assessment / research artifacts that exist).
- The task ledger (`tasks/`, `todo.md`, or the Progress Ledger items) when present.
- The current phase (passed as `--phase <phase>`).
- Findings / pending review todos (`todos/*-pending-*.md`) when present.
- The git diff -- objective working state: branch, HEAD, dirty status, an uncommitted lossless patch (tracked `git diff HEAD` PLUS every untracked, non-ignored file as an added-file diff).

The engine gathers all of this with pure local file + git operations. It NEVER forces a commit and NEVER clobbers an existing instruction file.

## The guarded cache-resolve one-liner

Mirror the deepseek/live-wires dual-cache resolve idiom. Resolve the engine from the plugin cache, verify it is present AND executable, then fire `write`:

```bash
ENGINE=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ENGINE=$(ls -t "$CACHE"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)
  [ -n "$ENGINE" ] && break
done
if [ -n "$ENGINE" ] && [ -x "$ENGINE" ]; then bash "$ENGINE" write --phase "<phase>"; fi
```

The `[ -n "$ENGINE" ]` guard covers "airlift not installed" (resolve returned empty). The `[ -x "$ENGINE" ]` guard covers "resolved a path but it is not executable." BOTH guards must sit within 3 lines of the `airlift-engine.sh` invocation.

## No-op when absent

Airlift is OPTIONAL. If the resolve loop finds no engine (or the engine is not executable), skip silently -- do NOT warn, do NOT block, do NOT degrade any pipeline step. The checkpoint is a best-effort safety net layered on top of the pipeline, never a gate.

## Tier-1 deterministic: no model budget

The checkpoint is tier-1 deterministic. It requires NO model budget, NO network, and NO AI API call -- it is pure local file + git work. That is the whole point: it can fire the instant a budget warning appears, or even after the model has gone dark. NEVER introduce a model call, agent dispatch, or LLM API request into the checkpoint path. Tier 2 (agent enrichment) and Tier 3 (ccusage early warning) are best-effort bonuses; the tier-1 checkpoint is the guarantee that survives a near-dead session.

## Early-warning trip behavior

When an early-warning signal trips (e.g. a ccusage budget threshold is crossed mid-run), do not wait for the next natural phase boundary:

1. Force an immediate checkpoint -- run the guarded resolve one-liner with the current `--phase` right away.
2. Surface the resume banner so the operator sees the bundle exists and knows the resume prompt is ready.

A forced checkpoint on an early-warning trip uses the same tier-1 deterministic path -- still no model budget -- so it is safe to fire even when the session is nearly out of budget.
