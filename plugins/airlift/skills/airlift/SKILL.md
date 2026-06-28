---
name: airlift
description: Model- and harness-agnostic session handoff triggers for "session handoff", "usage cap", "resume in another model", "checkpoint before I run out", "hand off to Codex", "hand off to DeepSeek", "hand off to Gemini", "rate limit", "continue where I left off", and ".airlift bundle" requests.
argument-hint: "[out|in|install] [target-harness|bundle-path]"
---

# Airlift

## What airlift is

Airlift is a model- and harness-agnostic session handoff capability. Its goal is to make a usage cap, rate limit, or model switch a non-event by preserving objective state, next steps, verification commands, and local git context in a small `.airlift/` bundle.

Use it when the user asks for session handoff, a checkpoint before they run out, resume in another model, hand off to Codex, DeepSeek, or Gemini, rate limit recovery, or continue where I left off.

## The .airlift/ bundle contract

`HANDOFF.md` is the human-readable handoff. It uses these sections:

- `Objective`
- `Status`
- `Next steps`
- `Gotchas-traps`
- `Key files & symbols`
- `How to verify`
- `Environment notes`

`state.json` is the machine-readable handoff state:

```json
{
  "schemaVersion": 1,
  "seq": 1,
  "timestamp": "2026-06-28T00:00:00Z",
  "source": {
    "harness": "claude-code",
    "model": "unknown"
  },
  "targets": ["codex"],
  "git": {
    "branch": "feature/example",
    "head": "abcdef0",
    "dirty": true
  },
  "phase": "handoff",
  "artifacts": {}
}
```

`uncommitted.patch` is `git diff HEAD`. If the tree is clean, write an empty patch file and note in `HANDOFF.md` that there were no uncommitted changes at checkpoint time.

`RESUME_PROMPT.md` is a harness-neutral seed prompt that tells the next model how to read `HANDOFF.md`, inspect `state.json`, apply or review `uncommitted.patch` if needed, and continue from the listed next steps.

## Three tiers

1. Deterministic continuous checkpoint: the safety net. It spends zero model budget, uses pure shell plus `git diff`, and requires no network.
2. Agent-authored enrichment: the current agent improves `HANDOFF.md` and `RESUME_PROMPT.md` with decisions, risks, and verification notes while budget remains.
3. `ccusage` early-warning bonus: optional warning support that can prompt a handoff before the user hits a cap.

## The marker block

Airlift installs an idempotent marker block in harness instruction files:

```markdown
<!-- airlift:start -->
[airlift instructions live here]
<!-- airlift:end -->
```

Append the block to `CLAUDE.md`, `AGENTS.md`, or `GEMINI.md` as appropriate. If the block already exists, replace it in place. Never clobber the rest of the instruction file.

## Harness profiles

Harness profile data lives in `${CLAUDE_SKILL_DIR}/references/harness-profiles.json`.

The registry is keyed by harness id. Unknown targets fall back to the universal resume path: paste `RESUME_PROMPT.md` into a new session.

`resume-via-deepseek` and `resume-via-gemini` are first-class paths through the existing DeepSeek and Gemini delegate plugins when they are installed.

## Honest limits

Tier 1 deterministic checkpointing is the safety net.

Tier 3 early warning is a bonus, not a guarantee.

Claude Code `statusLine` `rate_limits.five_hour.used_percentage` is a real signal, but only for Pro/Max after the first API response, and it may be absent.

`ccusage` is a cost-based estimate of the 5-hour block, not the weekly cap.

The exact hard cutoff and weekly-cap interaction are unpredictable.

No supported real-time usage API or hook exists. Issue `anthropics/claude-code#38380` was closed as not planned.

Native session-file reconstruction is out of scope.
