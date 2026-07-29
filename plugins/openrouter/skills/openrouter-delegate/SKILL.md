---
name: openrouter-delegate
description: Delegate policy-selected review, security analysis, second-opinion analysis, config/doc generation, and bounded execution to quality- and cost-ranked OpenRouter model slugs. Kimi K3 is the quality-first default and GLM-5.2 is the economical fallback. Powers the pipeline cascade's OpenRouter rail, generic review-agent runner, openrouter-exec runner, and dm-review external routing. Invoke with /openrouter for direct delegation.
---

# OpenRouter Delegation

Invoke OpenRouter for coding tasks where model quality, cost, or large context make it the right rail. Coding uses Codex and OpenRouter; Claude is reserved for non-coding work.

OpenRouter exposes many models behind one OpenAI-compatible endpoint. This plugin pins **Kimi K3** (`moonshotai/kimi-k3`) as the quality-first default and security-analysis head, with **GLM-5.2** (`z-ai/glm-5.2`) as its immediate capacity fallback. Both carry 1M-token context.

## One-Shot vs Agentic (read first)

The wrapper (`references/openrouter-wrapper.sh`) is a **single-turn completion call**. It returns text; it does not read/write files or run a tool loop.

Pipeline agentic execution is handled by `plugins/pipeline/references/openrouter-exec.sh`, which asks OpenRouter for a unified diff, applies it in the worktree, runs fixed structural validation, commits, and emits `implementedBy: openrouter` plus usage. Project verification is explicitly deferred to the native Codex reviewer so model-modified repository code never gains host command authority. Use that runner only for config/docs/mechanical-logic chunks selected by `plugins/pipeline/references/routing-policy.json`.

- **Valid uses:** big-diff analysis, code review, second-opinion analysis, and config/doc text generation the caller then writes to disk.
- **Invalid use:** complex autonomous chunk implementation that needs exploratory tool use, visual review, or cross-chunk judgment. For that work, the pipeline cascade returns to Codex or an eligible agentic OpenRouter rung. Never pipe raw wrapper text in as a chunk implementation.

## When to Delegate

| Advantage | Use Case | Why OpenRouter |
|-----------|----------|----------------|
| **Quality-first analysis** | Security, big-diff review, pattern analysis, second opinions | Kimi K3 leads eligible OpenRouter analysis while independent Codex review remains the consequential sign-off. |
| **1M-token context** | Bulk read, docs, config, and full-diff synthesis at any diff size | No truncation needed. Kimi K3 and GLM-5.2 both hold large context. |
| **Provider routing** | Privacy / throughput control | Per-request provider preferences (`OPENROUTER_ZDR=1` for no-train/no-retain providers). |
| **Capacity relief** | Pipeline / review runs burning Codex quota | Every eligible token routed to OpenRouter preserves Codex subscription headroom. |

## When NOT to Delegate

- Autonomous chunk implementation (single-turn; no file I/O or tool loop -- see above)
- Tasks requiring Claude's conversation context (OpenRouter calls are stateless)
- Tasks requiring MCP server access
- Sole-provider security completion (Kimi may lead analysis, but Codex sign-off remains mandatory)

### Security Boundary (hard rule)

**Kimi K3 may lead security analysis, but never replaces the independent Codex security reviewer.** Enforce the OpenRouter-owned `references/delegation-security-policy.json` immediately before every delegation. Pipeline carries a validated mirror for self-contained planning, but the installed OpenRouter policy is authoritative at runtime:

- **Threat/content boundary.** Inspect the exact bytes becoming OpenRouter system or user content. Decline high-confidence credentials, private keys, authenticated DSNs, access/session tokens, and explicitly classified private or regulated values. Recognized placeholders such as `<token>`, `REDACTED`, `example`, and environment-variable references are safe.
- **No identity or path embargo.** Model nationality, vendor jurisdiction, security-looking directories, `.env` references, header names, and environment-variable names are not disclosure evidence. Non-secret auth, federation, deploy, and security code may pass.
- **Execution mode -- bounded diffs only.** Accept only a non-empty validated unified diff whose normalized paths are all in the caller's exact owned-path list. The model has no command or verification authority. The runner performs only fixed structural Git checks; project build/test commands are deferred to the native Codex reviewer.
- **Mechanical-review and artifact-review modes.** Mechanical review scans complete per-file diff sections (including removed lines), emits eligible sections, and returns declined path names for local Codex coverage. Artifact review scans exact bytes and remains all-or-nothing.
- **Artifact-delegation mode.** Call `delegation-boundary.sh --mode artifact-delegation --policy POLICY --content-file FILE [--content-file FILE ...]` for arbitrary local text that will become OpenRouter content. Every explicit file is scanned byte-for-byte; the mode accepts no changed-file, diff, output-path, or execution authority.
- **Independent sign-off.** High-consequence security work may use OpenRouter after these controls pass, but completion still requires independent Codex security approval.
- **Intended lanes.** Security analysis with independent Codex sign-off, style, duplication, pattern-recognition, large-diff triage, and doc consistency.

## Invocation Protocol

Load the full protocol from `${CLAUDE_SKILL_DIR}/references/invocation-protocol.md`. It covers the wrapper's positional argument shape, workload-aware provider preferences (`OPENROUTER_WORKLOAD`, `OPENROUTER_ZDR`, `OPENROUTER_REQUIRE_PARAMS`, `OPENROUTER_PROVIDER_SORT`), streamed response handling, native fallback to a second model slug, layered timeouts, and content-free success/failure receipts.

Key rules: always set an overall timeout, always use the wrapper for automated
flows, and pipe large prompts via stdin (`-` as the prompt arg). The wrapper
privately JSON-encodes the prompt, assembles the streamed deltas, and prints the
model's text directly. All failures are graceful skips with content-free
receipts when requested.

## Model Selection

Load the decision table from `${CLAUDE_SKILL_DIR}/references/model-selection.md`. It maps task types to model slugs, timeouts, and the fallback chain.

**Default model:** `moonshotai/kimi-k3` (Kimi K3, 1M context). **Immediate fallback:** `z-ai/glm-5.2`.

**Provider-origin invariant:** OpenRouter primary and fallback slugs must never begin with `openai/` or `anthropic/`. OpenAI runs only through native Codex CLI capability; Anthropic runs only through native Claude CLI capability. This is an operational provenance boundary, not a nationality or jurisdiction embargo.

## MCP Control Plane

When the official OpenRouter MCP is available, load
`${CLAUDE_SKILL_DIR}/references/mcp-control-plane.md`. Use its read-only tools to
refresh model identity, endpoints, provider slugs, benchmarks, credits, and
documentation before changing the durable Matrix.

The MCP is discovery/observability only for automated workflows. Do not replace
the direct API runner with `send-message`: the runner owns the team key,
    exact-digest or Pipeline trusted-boundary authorization, timeouts, provider controls, fallback
chain, and content-free receipts. MCP absence never silently changes the
selected model.

## Prompt Engineering

Load templates from `${CLAUDE_SKILL_DIR}/references/prompt-templates.md`. Key principles:

1. **Self-contained prompts.** OpenRouter has no conversation context. Every prompt must include all necessary information.
2. **Structured output requests.** For dm-review integration, request P1/P2/P3 findings in the format the consolidator consumes.
3. **System prompt via env.** The wrapper takes the system prompt from `OPENROUTER_SYSTEM`; task content is the prompt argument (or stdin).

## Available Agents

| Agent | File | Purpose |
|-------|------|---------|
| **openrouter-agent-runner** | `plugins/openrouter/agents/workflow/openrouter-agent-runner.md` | Runs any eligible review-agent criteria through a policy-selected full OpenRouter model slug |
| **openrouter-bulk-analyst** | `plugins/openrouter/agents/review/openrouter-bulk-analyst.md` | Eligible full-diff-section review using Kimi K3 with a GLM-5.2 OpenRouter fallback |

## Prerequisites

OpenRouter API key must be set:

```bash
export OPENROUTER_API_KEY="sk-or-..."

# Resolve WORKFLOW_KERNEL once per caller using workflow-kernel's
# runtime-resolution contract, then select one coherent OpenRouter bundle.
: "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh first}"
ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && ACTIVE_HOST="codex"
if [ -n "$ACTIVE_HOST" ]; then
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.7.1 --active-host "$ACTIVE_HOST" \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/mcp-control-plane.md \
    --required-executable skills/openrouter-delegate/references/payload-authorization.sh)
else
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.7.1 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/mcp-control-plane.md \
    --required-executable skills/openrouter-delegate/references/payload-authorization.sh)
fi
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
[ -x "$WRAPPER_PATH" ] || exit 1

# Verify the installed low-level assets without transmitting data. Use the
# canonical /openrouter workflow for an authorized live authentication probe.
test -x "$WRAPPER_PATH"
```

The invoking session must have Bash permissions for `curl`. If the first invocation is blocked by permissions, report to the user and skip gracefully. Never commit `OPENROUTER_API_KEY` -- keep it in environment or settings only.
