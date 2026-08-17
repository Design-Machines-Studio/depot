---
name: openrouter-delegate
description: Use when the user explicitly asks to delegate work to OpenRouter; requests a routed exact model; wants cheap bounded config/docs work, long-context or bulk review, an independent second opinion, or subscription relief. Routes focused security to Kimi K3, routine documentation/test review and bounded execution to DeepSeek, bulk/independent review to Qwen3.8 Max, demanding escalation to Grok 4.6, and economical fallback to Luna. Do not trigger for ordinary coding, review, pipeline, commit, or push requests that do not mention OpenRouter, a routed model, cost offload, or large-context analysis.
---

# OpenRouter Delegation

Use OpenRouter directly for explicitly requested analysis on a trusted
developer workstation. A configured `OPENROUTER_API_KEY` or validated
`OPENROUTER_API_KEY_FILE`, a coherent installed bundle, and an automatically
screened eligible payload are sufficient; no second approval is required.

OpenRouter exposes many models behind one OpenAI-compatible endpoint. Ordered
role lists select exact versioned slugs: DeepSeek handles cheap bounded work and
routine review, Qwen3.8 Max handles bulk and independent judgment, Grok 4.6 is
the demanding escalation, Luna is a mechanical fallback, and Kimi K3 is
reserved for focused applicable security analysis.

## One-Shot vs Agentic (read first)

The wrapper (`references/openrouter-wrapper.sh`) is a **single-turn completion call**. It returns text; it does not read/write files or run a tool loop.

The bounded Pipeline executor uses the same configured-key wrapper path for its
already-authorized non-sensitive config/docs/mechanical workload. It still
requires an exact owned-path allowlist, accepts only a validated unified diff,
and defers correctness verification to native Codex.

- **Valid current uses:** explicitly requested direct interactive big-diff
  analysis, code review, second-opinion analysis, and config/doc text generation
  after the automatic disclosure boundary accepts the exact outbound bytes.
- **Invalid use:** complex autonomous chunk implementation that needs exploratory tool use, visual review, or cross-chunk judgment. For that work, the pipeline cascade returns to Codex or an eligible agentic OpenRouter rung. Never pipe raw wrapper text in as a chunk implementation.

## When to Delegate

| Advantage | Use Case | Why OpenRouter |
|-----------|----------|----------------|
| **Role-specific analysis** | Security, big-diff review, pattern analysis, second opinions | Kimi leads only security; Qwen, DeepSeek, and Grok own the ordinary analysis roles. |
| **Long context** | Bulk read, docs, config, and full-diff synthesis | The matrix records both model and top-provider limits; callers must respect the smaller current limit. |
| **Provider routing** | Privacy / throughput control | Per-request provider preferences (`OPENROUTER_ZDR=1` for no-train/no-retain providers). |
| **Capacity relief** | Eligible dm-review and bounded Pipeline lanes | Configured-key dispatch may preserve Codex subscription headroom without interrupting the run. |

## When NOT to Delegate

- Autonomous chunk implementation (single-turn; no file I/O or tool loop -- see above)
- Tasks requiring Claude's conversation context (OpenRouter calls are stateless)
- Tasks requiring MCP server access
- Sole-provider security completion (Kimi may lead analysis, but independent non-implementing-family sign-off remains mandatory)

### Security Boundary (hard rule)

**Kimi K3 may lead security analysis, but never replaces the independent non-implementing-family security reviewer.** Enforce the OpenRouter-owned `references/delegation-security-policy.json` immediately before every delegation. Pipeline carries a validated mirror for self-contained planning, but the installed OpenRouter policy is authoritative at runtime:

- **Threat/content boundary.** Inspect the exact bytes becoming OpenRouter system or user content. Decline high-confidence credentials, private keys, authenticated DSNs, access/session tokens, and explicitly classified private or regulated values. Names, syntactically valid shell/CI source references, and unmistakable `*-secret-not-for-proof` / `*-access-not-for-proof` test sentinels are safe; actual values remain refused.
- **No identity or path embargo.** Model nationality, vendor jurisdiction, security-looking directories, `.env` references, header names, and environment-variable names are not disclosure evidence. Non-secret auth, federation, deploy, and security code may pass.
- **Execution mode -- bounded diffs only.** Accept only a non-empty validated unified diff whose normalized paths are all in the caller's exact owned-path list. The model has no command or verification authority. The runner performs only fixed structural Git checks; project build/test commands are deferred to the native Codex reviewer.
- **Mechanical-review and artifact-review modes.** Mechanical review scans complete per-file diff sections (including removed lines), emits eligible sections, and returns declined path names for local Codex coverage. Artifact review scans exact bytes and remains all-or-nothing.
- **Artifact-delegation mode.** Call `delegation-boundary.sh --mode artifact-delegation --policy POLICY --content-file FILE [--content-file FILE ...]` for arbitrary local text that will become OpenRouter content. Every explicit file is scanned byte-for-byte; the mode accepts no changed-file, diff, output-path, or execution authority.
- **Independent sign-off.** High-consequence security work may use OpenRouter after these controls pass, but completion still requires a reviewer family different from the implementer.
- **Intended lanes.** Security analysis with independent non-implementing-family sign-off, style, duplication, pattern-recognition, large-diff triage, and doc consistency.

A safe payload that is unexpectedly declined should be fixed at this shared
boundary and retried unchanged after the repair; do not manually narrow or
rewrite harmless review input. A genuine disclosure decline gets one clear
refusal and falls back to the native harness without repeated OpenRouter
attempts.

## Invocation Protocol

Load the full protocol from `${CLAUDE_SKILL_DIR}/references/invocation-protocol.md`. It covers the wrapper's positional argument shape, workload-aware provider preferences (`OPENROUTER_WORKLOAD`, `OPENROUTER_ZDR`, `OPENROUTER_REQUIRE_PARAMS`, `OPENROUTER_PROVIDER_SORT`), streamed response handling, native fallback to a second model slug, layered timeouts, and content-free success/failure receipts.

Key rules: always set an overall timeout, use the configured-key
`trusted-boundary` workflow in production, and pipe large prompts via stdin
(`-` as the prompt arg). The wrapper
privately JSON-encodes the prompt, assembles the streamed deltas, and prints the
model's text directly. All failures are graceful skips with content-free
receipts when requested.

## Model Selection

Load the decision table from `${CLAUDE_SKILL_DIR}/references/model-selection.md`. It maps task types to model slugs, timeouts, and the fallback chain.

**Default model:** `qwen/qwen3.8-max`. **Immediate fallback:** `x-ai/grok-4.6`.

**Provider-origin invariant:** OpenRouter primary and fallback slugs must never begin with `anthropic/`. OpenAI may run through native Codex or the receipted OpenRouter API rail; Anthropic runs only through native Claude capability.

## MCP Control Plane

When the official OpenRouter MCP is available, load
`${CLAUDE_SKILL_DIR}/references/mcp-control-plane.md`. Use its read-only tools to
refresh model identity, endpoints, provider slugs, benchmarks, credits, and
documentation before changing the durable Matrix.

The MCP is discovery/observability only for automated workflows. Do not replace
the direct API runner with `send-message`: `/openrouter` retains its automatic
disclosure boundary, timeouts, provider controls, fallback chain, and
content-free receipts. dm-review and bounded Pipeline use that same
configured-key transport under their existing applicability rules.

## Prompt Engineering

Load templates from `${CLAUDE_SKILL_DIR}/references/prompt-templates.md`. Key principles:

1. **Self-contained prompts.** OpenRouter has no conversation context. Every prompt must include all necessary information.
2. **Structured output requests.** For dm-review integration, request P1/P2/P3 findings in the format the consolidator consumes.
3. **Exact prompt bytes.** Prefer `OPENROUTER_SYSTEM_FILE` for screened system
   prompt files and unset inherited `OPENROUTER_SYSTEM`; task content is the
   prompt argument or stdin and is materialized byte-for-byte by the wrapper.

## Available Agents

| Agent | File | Purpose |
|-------|------|---------|
| **openrouter-agent-runner** | `plugins/openrouter/agents/workflow/openrouter-agent-runner.md` | Runs any eligible review-agent criteria through a policy-selected full OpenRouter model slug |
| **openrouter-bulk-analyst** | `plugins/openrouter/agents/review/openrouter-bulk-analyst.md` | Eligible full-diff-section review using Qwen3.8 Max with DeepSeek V4 Pro 0813 fallback |

## Prerequisites

An OpenRouter API key or validated key file enables eligible direct, dm-review,
and bounded Pipeline dispatch after automatic payload screening:

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
    --minimum-version 1.14.0 --active-host "$ACTIVE_HOST" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
    --required-asset skills/openrouter-delegate/references/mcp-control-plane.md \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh)
else
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.14.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
    --required-asset skills/openrouter-delegate/references/mcp-control-plane.md \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh)
fi
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
[ -x "$WRAPPER_PATH" ] || exit 1

# Verify the installed low-level assets without transmitting data.
test -x "$WRAPPER_PATH"
```

The invoking session must have Bash permissions for `curl`. If the first invocation is blocked by permissions, report to the user and skip gracefully. Never commit `OPENROUTER_API_KEY` -- keep it in environment or settings only.
