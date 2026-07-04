---
name: openrouter-delegate
description: Delegate policy-selected review, second-opinion analysis, config/doc generation, and bounded OpenRouter execution to GLM-5.2 / DeepSeek V4 at lower cost than Anthropic. GLM-5.2 (z-ai/glm-5.2, 1M context) is the default quality-per-dollar model. Powers the pipeline cascade's OpenRouter rail, openrouter-exec runner, and dm-review external routing. Invoke with /openrouter for direct delegation.
---

# OpenRouter Delegation

Invoke the OpenRouter API as a supplementary provider for tasks where cost-per-token or large-context capacity matters. OpenRouter is always supplementary -- Opus remains the primary thinker, and Claude's main loop is never routed through OpenRouter.

OpenRouter exposes many models behind one OpenAI-compatible endpoint. This plugin pins **GLM-5.2** (`z-ai/glm-5.2`) as the default quality-per-dollar model, with **DeepSeek V4** (`deepseek/deepseek-v4-pro`) as the alternate. Both carry 1M-token context.

## One-Shot vs Agentic (read first)

The wrapper (`references/openrouter-wrapper.sh`) is a **single-turn completion call**. It returns text; it does not read/write files or run a tool loop.

Pipeline agentic execution is handled by `plugins/pipeline/references/openrouter-exec.sh`, which asks OpenRouter for a unified diff, applies it in the worktree, runs verification, commits, and emits `implementedBy: openrouter` plus usage. Use that runner only for config/docs/mechanical-logic chunks selected by `plugins/pipeline/references/routing-policy.json`.

- **Valid uses:** big-diff analysis, code review, second-opinion analysis, and config/doc text generation the caller then writes to disk.
- **Invalid use:** complex autonomous chunk implementation that needs exploratory tool use, visual review, or cross-chunk judgment. For that work, the pipeline cascade descends to Codex/Claude. Never pipe raw wrapper text in as a chunk implementation.

## When to Delegate

| Advantage | Use Case | Why OpenRouter |
|-----------|----------|----------------|
| **Quality-per-dollar** | Big-diff review, pattern analysis, second opinions | GLM-5.2 at a fraction of frontier cost; doesn't burn Anthropic Max quota. |
| **1M-token context** | Bulk read, docs, config, and full-diff synthesis at any diff size | No truncation needed. GLM-5.2 and DeepSeek V4 both hold large context. |
| **Provider routing** | Privacy / throughput control | Per-request provider preferences (`OPENROUTER_ZDR=1` for no-train/no-retain providers). |
| **Capacity relief** | Pipeline / review runs burning Max quota | Every token routed to OpenRouter is a token NOT counted against the Anthropic weekly limit. |

## When NOT to Delegate

- Autonomous chunk implementation (single-turn; no file I/O or tool loop -- see above)
- Tasks requiring Claude's conversation context (OpenRouter calls are stateless)
- Tasks requiring MCP server access
- Adversarial review, ambiguity detection, or security-critical analysis (keep on Anthropic)

### Security Boundary (hard rule)

**Third-party models (GLM-5.2, DeepSeek V4) are bulk pattern reviewers, never security reviewers.** Enforce `security` in `plugins/pipeline/references/routing-policy.json` before any delegation:

- **Path exclusions -- route Anthropic-side.** If the diff/context touches `internal/auth/**`, `internal/federation/**`, `**/secretbox*`, `**/destructive_confirmation*`, `internal/baseplate/email/settings*`, `deploy/**`, or `*.env*`, DECLINE and return the chunk to the Anthropic-native reviewer. A single matching file taints the whole chunk. This applies to the one-shot delegate AND the `openrouter-exec` agentic runner.
- **Content redaction.** Strip environment values, API tokens/keys, connection strings/DSNs, and production hostnames-with-paths before sending. If they cannot be stripped, do not send that content -- return it to Anthropic-side review.
- **Intended lanes.** Style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency route off-Anthropic freely when no boundary is tripped.

## Invocation Protocol

Load the full protocol from `${CLAUDE_SKILL_DIR}/references/invocation-protocol.md`. It covers the wrapper's positional argument shape, the per-request provider preferences (`OPENROUTER_ZDR`, `OPENROUTER_REQUIRE_PARAMS`, `OPENROUTER_PROVIDER_SORT`), HTTP status handling, the rate-limit fallback to a second model slug, and response parsing.

Key rules: always set a timeout, always use the wrapper for automated flows, pipe large prompts via stdin (`-` as the prompt arg). The wrapper prints the model's text content directly (it already extracts `.choices[0].message.content`). All failures are graceful skips.

## Model Selection

Load the decision table from `${CLAUDE_SKILL_DIR}/references/model-selection.md`. It maps task types to model slugs, timeouts, and the fallback chain.

**Default model:** `z-ai/glm-5.2` (GLM-5.2, 1M context). **Alternate / fallback:** `deepseek/deepseek-v4-pro`.

## Prompt Engineering

Load templates from `${CLAUDE_SKILL_DIR}/references/prompt-templates.md`. Key principles:

1. **Self-contained prompts.** OpenRouter has no conversation context. Every prompt must include all necessary information.
2. **Structured output requests.** For dm-review integration, request P1/P2/P3 findings in the format the consolidator consumes.
3. **System prompt via env.** The wrapper takes the system prompt from `OPENROUTER_SYSTEM`; task content is the prompt argument (or stdin).

## Available Agents

| Agent | File | Purpose |
|-------|------|---------|
| **openrouter-bulk-analyst** | `plugins/openrouter/agents/review/openrouter-bulk-analyst.md` | Full-diff review using GLM-5.2 (DeepSeek V4 fallback) 1M context |

## Prerequisites

OpenRouter API key must be set:

```bash
export OPENROUTER_API_KEY="sk-or-..."

# Resolve the wrapper via the plugin cache (works from any CWD, incl. worktrees)
WRAPPER_PATH=""
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER_PATH=$(ls -t "$CACHE_ROOT"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER_PATH" ] && break
done
if [ -z "$WRAPPER_PATH" ] || [ ! -x "$WRAPPER_PATH" ]; then
  echo "openrouter wrapper not found in plugin cache" >&2
  exit 1
fi

# Verify authentication (privacy-pinned)
OPENROUTER_ZDR=1 bash "$WRAPPER_PATH" "z-ai/glm-5.2" "test" 30
```

The invoking session must have Bash permissions for `curl`. If the first invocation is blocked by permissions, report to the user and skip gracefully. Never commit `OPENROUTER_API_KEY` -- keep it in environment or settings only.
