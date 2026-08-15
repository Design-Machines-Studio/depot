# openrouter

OpenRouter API provider plugin (leaf). Delegates policy-routed review, bulk / large-context diff analysis, second-opinion review, one-shot text generation, and bounded agentic execution to quality- and cost-ranked OpenRouter model slugs over one endpoint. The matrix includes GPT-5.6 Terra and Luna, GLM-5.2 (`z-ai/glm-5.2`), DeepSeek V4, and Kimi K3. OpenAI models may run through OpenRouter as an economical API rail; Anthropic remains native Claude-only.

> **Current release mode:** a configured key plus one coherent installed bundle
> makes OpenRouter available for direct, eligible dm-review, and bounded
> Pipeline use after automatic payload screening. No user-approval step or
> broker probe is required.

The direct API runner is the execution data plane. The optional official
OpenRouter MCP is a read-only-first control plane for live model/provider
discovery, benchmarks, credits, documentation, and generation inspection. See
`skills/openrouter-delegate/references/mcp-control-plane.md`.

The direct runner uses streamed chat completions, OpenRouter-native ordered
model fallback, separate connection/first-byte/idle/overall watchdogs, and
content-free success or failure receipts. Routine direct and bulk workloads
prefer throughput; consequential quality and security workloads retain
quality-first Exacto routing.

Long-running generations use a one-hour completion budget by default and two
hours for very large or bulk review. A 30-second connection timeout plus
10-minute first-byte and stream-idle watchdogs still terminate dead transports
without confusing one model-call budget with the duration of the full Pipeline
run.

## What it routes

Task-to-model routing is governed by `plugins/pipeline/references/routing-policy.json`; the installed OpenRouter delegation policy owns the security boundary. The following matrix is available to configured-key dm-review and bounded Pipeline dispatch and remains observable through dry-run routing:

- **Primary external provider** for `pattern-recognition-specialist`, `code-simplicity-reviewer`, `doc-sync-reviewer`, and `test-coverage-reviewer`; each lane uses the model and fallback model selected by policy.
- **Primary Kimi K3 security-analysis lens**, paired with mandatory independent non-implementing-family full-diff sign-off.
- **Primary Kimi K3 bulk lane** for large-context / large-diff first-pass triage.
- The DeepSeek V4 Flash 0731-headed cascade rail for `config` / `docs` / `mechanical-logic` chunk execution via `openrouter-exec`, with Grok 4.5 escalation and GLM-5.2 only as the experimental last fallback.

## Security boundary (non-negotiable)

**Configured key and automatic disclosure classification are the active controls.** A configured supported key input authorizes eligible trusted-workstation development use; the exact outbound bytes must still pass the disclosure boundary before provider contact.

The canonical policy is `skills/openrouter-delegate/references/delegation-security-policy.json`; Pipeline carries a validated mirror for planning. Every delegation path enforces it before invoking the wrapper:

- **Threat/content classification.** High-confidence credentials, private keys, authenticated DSNs, access/session tokens, and explicitly classified private values keep that file-diff section local. Eligible sections continue to OpenRouter; security-looking paths, vendors, nationalities, jurisdictions, and placeholder names do not create an embargo.
- **Bounded execution.** Model output is accepted only as a validated unified diff restricted to the caller's exact owned-path allowlist. The runner performs fixed structural Git validation and allowlist-only staging; executable project verification is deferred to native Codex review.
- **Intended lanes.** Security analysis with independent non-implementing-family sign-off, style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency.

High-consequence security completion still requires a reviewer family different from the implementer. GLM, DeepSeek, Kimi, and other third-party models are not banned by nationality.

Every live caller selects one coherent installed plugin root with workflow-kernel `resolve-plugin-bundle`, then derives its wrapper, policy, boundary, protocols, and templates from that root. Semantic version wins over mtime; the active host breaks only equal-version ties. Durable receipts keep the version, cache class, and reason, never the absolute home path.

## Requirements

- `OPENROUTER_API_KEY` or a validated `OPENROUTER_API_KEY_FILE` is required for every live wrapper transmission and activates eligible configured-key lanes.
- `OPENROUTER_ZDR=1` opt-in to pin zero-data-retention providers for genuinely sensitive material (privacy demoted by default: Quality > Price > Speed > Provider privacy).
- `OPENROUTER_WORKLOAD=quality|security|direct|bulk|mechanical` selects the
  default provider-routing strategy; explicit provider sort/order overrides it.
- Canonical disclosure scanning rejects ineligible exact outbound bytes before
  provider contact. Active callers scan private system/user files once and
  immediately pass those same files to the wrapper.
- Use provider-side per-key spending limits for runaway-cost control.
- Optional OpenRouter MCP: `codex mcp add openrouter --url https://mcp.openrouter.ai/mcp`, then `codex mcp login openrouter`. Its expiring OAuth key does not replace the persistent team API key.

## Budgets and content-safe HTTP failures

OpenRouter account credit balance, organization monthly budget, and per-key
spending limit are independent controls. A positive credit balance and a
successful `/auth/key` lookup do not prove that the organization monthly budget
or the key's spending limit has headroom. When the organization monthly budget
is exhausted, its administrator must raise or reset that limit; buying credits
or replacing an otherwise valid key is not the remedy for that condition.

HTTP failure receipts keep `failureKind: http_error` and expose only the closed,
nullable `failureReason` vocabulary:

- `organization_monthly_budget_exceeded`
- `key_permission_denied`
- `guardrail_blocked`
- `insufficient_credits`
- `rate_limited`
- `unknown_http_error`

The wrapper derives stderr from fixed labels for those values. Provider
messages, moderation reasons or patterns, `flagged_input`, arbitrary error
metadata, `openrouter_metadata`, prompts, and raw response bodies remain inside
the private temporary run directory and are not printed or stored in receipts.
