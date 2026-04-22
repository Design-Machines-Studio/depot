---
name: gemini-delegate
description: Delegate tasks to Gemini CLI for Google search grounding with citations, large diff analysis using 2M token context, or Python code execution sandbox. Use when Claude needs web research with cited sources, when diffs exceed truncation thresholds, when algorithm verification requires code execution, or when the user explicitly asks to use Gemini. Invoke with /gemini for direct delegation or /gemini-search for search-grounded queries.
---

# Gemini Delegation

Invoke Gemini CLI as a subagent for tasks where Gemini has a demonstrable advantage over Claude's native tools. Gemini is always supplementary — never a replacement for Claude's primary workflow.

## When to Delegate

| Advantage | Use Case | Why Gemini |
|-----------|----------|------------|
| **Google Search Grounding** | Web research, current best practices, framework docs | Auto-cites sources with URLs. More reliable than WebSearch for structured, authoritative results. |
| **2M Token Context** | Full diff analysis when diffs exceed 5000 lines | No truncation needed. Claude's dm-review truncates to 200 lines/file at this threshold. |
| **Code Execution Sandbox** | Algorithm verification, math validation, data transformation testing | Python sandbox with NumPy/SymPy. Claude can only analyze statically. |
| **Cost Efficiency** | Bulk factual lookups, simple extraction tasks | Flash-lite is extremely cheap for delegated grunt work. |

## When NOT to Delegate

- Tasks requiring Claude's conversation context (Gemini is stateless)
- Tasks requiring MCP server access (Gemini can't reach Claude's MCP servers)
- Tasks where Claude's native tools work well (don't delegate for delegation's sake)
- Interactive or multi-turn workflows (each Gemini call is a fresh session)

## Invocation Protocol

Load the full protocol from `${CLAUDE_SKILL_DIR}/references/invocation-protocol.md`. It covers CLI syntax, input methods (direct `-p` for short prompts, heredoc for large inputs), JSON response parsing (`{response, stats}`), error response format, the four failure modes (timeout, empty, malformed, rate limit), the **Fallback chain** wrapper (`references/gemini-wrapper.sh`) that walks `pro → flash → flash-lite` on real 429s (the CLI does not auto-fall-back), and shell safety rules.

Key rules: always wrap with `timeout`, always use `--yolo` for automated flows, always use heredoc with quoted delimiter (`<<'GEMINI_INPUT'`) for content containing code or user input. All failures are graceful skips.

## Model Selection

Load the full decision table from `${CLAUDE_SKILL_DIR}/references/model-selection.md`. It maps task types to models (`flash-lite`, `flash`, `pro`), timeouts, and expected latency.

**Rate limit fallback chain:** `pro` → `flash` → `flash-lite` → skip

## Prompt Engineering

Load templates from `${CLAUDE_SKILL_DIR}/references/prompt-templates.md`. Key principles:

1. **Self-contained prompts.** Gemini has no conversation context. Every prompt must include all necessary information — the task, the context, the expected output format, and any constraints.

2. **Structured output requests.** Always tell Gemini what format you need. For dm-review integration, request P1/P2/P3 findings. For research, request URL + title + excerpt structure.

3. **No tool assumptions.** Don't assume Gemini will use specific tools (search, code execution). Frame the prompt so the task is clear; Gemini decides which tools to invoke.

4. **Escape handling.** When piping code or diffs, use heredoc with quoted delimiter (`<<'GEMINI_INPUT'`) to prevent shell expansion.

## Available Agents

This skill provides three specialized agents for common delegation patterns:

| Agent | File | Purpose |
|-------|------|---------|
| **gemini-diff-analyst** | `plugins/gemini/agents/review/gemini-diff-analyst.md` | Full-diff review using 2M context |
| **gemini-search-grounded** | `plugins/gemini/agents/workflow/gemini-search-grounded.md` | Web research with cited sources |
| **gemini-code-executor** | `plugins/gemini/agents/workflow/gemini-code-executor.md` | Python sandbox code verification |

## Prerequisites

Gemini CLI must be installed and authenticated:

```bash
# Verify installation
which gemini  # Should return /opt/homebrew/bin/gemini or similar

# Verify authentication
gemini -p "test" -m flash-lite --output-format json --raw-output

# If not installed: npm install -g @google/gemini-cli
# If not authenticated: gemini auth login
```

The invoking Claude Code session must have Bash permissions for `gemini` commands. If the first invocation is blocked by permissions, report to the user and skip gracefully.
