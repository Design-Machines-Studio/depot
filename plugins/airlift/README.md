# airlift

Claude Code plugin for model- and harness-agnostic session handoff. Airlift turns usage caps, rate limits, and model switches into a documented checkpoint and resume workflow instead of a lost-context event.

## What This Plugin Provides

One auto-activating skill for session handoff planning and three slash commands for creating, consuming, and installing handoff support.

The core contract is a `.airlift/` bundle with deterministic files that any supported harness can read: `HANDOFF.md`, `state.json`, `uncommitted.patch`, and `RESUME_PROMPT.md`. `uncommitted.patch` is lossless -- it captures `git diff HEAD` plus every untracked, non-ignored file -- and the bundle is gitignored by default.

## Skills (auto-activating)

| Skill | Triggers when you're... |
|-------|------------------------|
| `airlift` | Preparing a session handoff, hitting a usage cap or rate limit, checkpointing before running out, or resuming in Claude Code, Codex, DeepSeek, Gemini, Kiro, or OpenCode |

## Commands

| Command | What it does |
|---------|-------------|
| `/airlift-out [--commit \| --no-commit] [note]` | Create or refresh a `.airlift/` handoff bundle from the current session (default no-commit patch capture) |
| `/airlift-in [path]` | Resume from an existing `.airlift/` handoff bundle in the current harness |
| `/airlift-install [wire \| unwire \| status]` | Wire/unwire the Tier-3 early-warning monitor in `settings.json` (statusLine chain + StopFailure hook), preserving the existing statusLine |

## Harness Profiles

Harness profiles live in `skills/airlift/references/harness-profiles.json`. The first registry includes Claude Code, Codex, DeepSeek, Gemini, Kiro, and OpenCode, with an explicit fallback for unknown targets: paste `RESUME_PROMPT.md` into a new session.

DeepSeek and Gemini are first-class resume targets through the existing delegate plugins when they are installed.

## Honest limits

Tier 1 deterministic checkpointing is the safety net. It uses shell and git state only, does not need network access, and does not spend model budget.

Tier 2 agent-authored enrichment can improve the handoff, but it depends on the current model's remaining budget and judgment.

Tier 3 early warning is a bonus. Claude Code `statusLine` `rate_limits.five_hour.used_percentage` is a real signal only for Pro/Max after the first API response and may be absent. `ccusage` is a cost-based estimate of the 5-hour block, not the weekly cap. Exact hard cutoffs and weekly-cap interaction are unpredictable, and there is no supported real-time usage API or hook. Native session-file reconstruction is out of scope.
