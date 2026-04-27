---
name: deepseek-delegate
description: Delegate tasks to DeepSeek V4 API for high-quality code analysis at lower cost than Sonnet. V4-Pro matches Opus 4.6 on SWE-bench (80.6%); V4-Flash handles mechanical checks at Haiku-tier cost. Use when offloading bulk diff review, code pattern analysis, or mechanical checks from Anthropic quota. Includes a generic agent runner that routes specific dm-review agents (pattern-recognition, code-simplicity, doc-sync, test-coverage) through DeepSeek when DEEPSEEK_API_KEY is set. Invoke with /deepseek for direct delegation.
---

# DeepSeek Delegation

Invoke DeepSeek V4 API as a supplementary provider for tasks where cost-per-token or capacity matters. DeepSeek is always supplementary -- Opus remains the primary thinker.

## When to Delegate

| Advantage | Use Case | Why DeepSeek |
|-----------|----------|--------------|
| **Sonnet-tier quality at lower cost** | Code review agents, pattern analysis, refactoring suggestions | V4-Pro scores 80.6% SWE-bench Verified, matches Opus 4.6. $1.74/MTok input vs Sonnet pricing. |
| **Bulk diff analysis** | Large diffs (>5K lines, >20 files) | 1M token context. No truncation needed. Doesn't burn Anthropic Max quota. |
| **Mechanical checks** | Anti-pattern scans, link rot, doc-sync verification | V4-Flash at $0.14/MTok for tasks that don't need deep reasoning. |
| **Capacity relief** | Pipeline runs burning through Max quota | Every token routed to DeepSeek is a token NOT counted against your Anthropic weekly limit. |

## When NOT to Delegate

- Tasks requiring Claude's conversation context (DeepSeek calls are stateless)
- Tasks requiring MCP server access (DeepSeek can't reach Claude's MCP servers)
- Adversarial review or ambiguity detection (Opus's reasoning edge matters here)
- Security-critical analysis (keep on Anthropic for liability and quality assurance)
- Interactive multi-turn workflows (each DeepSeek call is a fresh session)

## Invocation Protocol

Load the full protocol from `${CLAUDE_SKILL_DIR}/references/invocation-protocol.md`. It covers curl syntax, JSON escaping via python3, the wrapper script (`references/deepseek-wrapper.sh`) with its `v4-pro -> v4-flash` fallback chain, HTTP status handling, and response parsing.

Key rules: always set `--max-time` timeout, always use the wrapper for automated flows, always escape prompts via python3 JSON encoder (never embed raw user input in curl `-d`). All failures are graceful skips.

## Model Selection

Load the full decision table from `${CLAUDE_SKILL_DIR}/references/model-selection.md`. It maps task types to models (`v4-pro`, `v4-flash`), timeouts, and expected latency.

**Rate limit fallback chain:** `v4-pro` -> `v4-flash` -> skip

## Prompt Engineering

Load templates from `${CLAUDE_SKILL_DIR}/references/prompt-templates.md`. Key principles:

1. **Self-contained prompts.** DeepSeek has no conversation context. Every prompt must include all necessary information.
2. **Structured output requests.** Always tell DeepSeek what format you need. For dm-review integration, request P1/P2/P3 findings.
3. **Escape handling.** Use the wrapper's `-p` flag for short prompts. For large inputs, pipe via stdin.

## Available Agents

| Agent | File | Purpose |
|-------|------|---------|
| **deepseek-bulk-analyst** | `plugins/deepseek/agents/review/deepseek-bulk-analyst.md` | Full-diff review using 1M context |
| **deepseek-code-analyst** | `plugins/deepseek/agents/workflow/deepseek-code-analyst.md` | Code pattern analysis and refactoring review |

## Prerequisites

DeepSeek API key must be set:

```bash
export DEEPSEEK_API_KEY="sk-..."

# Verify authentication
bash plugins/deepseek/skills/deepseek-delegate/references/deepseek-wrapper.sh \
  -m v4-flash -p "test"
```

The invoking Claude Code session must have Bash permissions for `curl` commands. If the first invocation is blocked by permissions, report to the user and skip gracefully.
