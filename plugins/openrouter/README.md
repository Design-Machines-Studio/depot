# openrouter

OpenRouter API provider plugin (leaf). Delegates policy-routed review, bulk / large-context diff analysis, second-opinion review, one-shot text generation, and bounded agentic execution to exact versioned OpenRouter model slugs over one endpoint. The evidence matrix catalogs current candidates; model-router owns concrete candidate order while Pipeline and dm-review request provider-neutral roles. Anthropic remains native Claude-only.

> **Current release mode:** a configured key plus one coherent installed bundle
> makes OpenRouter available for direct, eligible dm-review, and bounded
> Pipeline use under the same input-eligibility rules as native Claude/Codex
> candidates. No user-approval step or broker probe is required.

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

Task-to-role intent is governed by each caller's provider-neutral policy;
`plugins/model-router/skills/model-router/references/role-policy.json` alone owns
concrete candidate order. OpenRouter owns its transport and response controls,
not a separate payload-content eligibility gate. Current candidate evidence remains observable through the
private router receipt and provider model matrix:

- **Primary external provider** for `pattern-recognition-specialist`, `code-simplicity-reviewer`, `doc-sync-reviewer`, and `test-coverage-reviewer`; each lane uses the model and fallback model selected by policy.
- **Kimi K3 only for focused applicable security analysis**, paired with mandatory independent non-implementing-family full-diff sign-off.
- **Qwen3.8 Max for bulk and ordinary independent review**, with DeepSeek V4 Pro 0813 or Grok 4.6 as role-specific fallbacks.
- **DeepSeek V4 Flash 0731 for routine documentation/test review and bounded `config` / `docs` / `mechanical-logic` execution**, with Luna as the routine-review fallback and Grok 4.6 as the bounded-execution escalation.

## Provider parity and bounded output (non-negotiable)

**A configured supported key authorizes trusted-workstation use under provider-neutral input rules.** Any prompt or evidence eligible for an available native Claude/Codex subscription candidate is eligible for OpenRouter. Callers never reject, redact, split, hold, or fall back because OpenRouter input contains secrets, credentials, authenticated endpoints, classified material, security code, deployment details, or other payload content.

- **Transport credentials.** Validate and load the OpenRouter API key from its supported environment or key-file source, keep it out of command arguments and receipts, and send it only in the authorization header.
- **Response controls.** Keep timeouts, response-model provenance, content-free receipts, non-empty output checks, and caller-owned format validation active.
- **Bounded execution.** Model output is accepted only as a validated unified diff restricted to the caller's exact owned-path allowlist. The runner performs fixed structural Git validation and allowlist-only staging; executable project verification is deferred to native Codex review.
- **Intended lanes.** Security analysis with independent non-implementing-family sign-off, style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency.

High-consequence security completion still requires a reviewer family different from the implementer. OpenRouter is transport provenance, not a model family. GLM 5.3 and GLM 5.3 Flash are catalogued as evidence but appear in no active ladder.

Every live caller selects one coherent installed plugin root with workflow-kernel `resolve-plugin-bundle`, then derives its wrapper, policy, boundary, protocols, and templates from that root. Semantic version wins over mtime; the active host breaks only equal-version ties. Durable receipts keep the version, cache class, and reason, never the absolute home path.

## Benchmark evidence

The manual `depot-role-v2` suite covers all nine roles with two distinct cases
each. It keeps raw and normalized output, digest-bound evaluator revisions,
confirmed identity provenance, and stage-attributed failures. Screens discover
opportunities only; they do not change routing. Promotion requires three
comparable successful attempts on every applicable distinct case plus the
existing production and policy gates. Benchmark-owned faults have no model
conclusion and must be repaired before more evidence is collected. Validated
quality and contextual efficiency lead interpretation; provider spend and
access remain separate guardrails.

## Requirements

- `OPENROUTER_API_KEY` or a validated `OPENROUTER_API_KEY_FILE` is required for every live wrapper transmission and activates eligible configured-key lanes.
- `OPENROUTER_ZDR=1` opt-in to pin zero-data-retention providers for genuinely sensitive material (privacy demoted by default: Quality > Price > Speed > Provider privacy).
- `OPENROUTER_WORKLOAD=quality|security|direct|bulk|mechanical` selects the
  default provider-routing strategy; explicit provider sort/order overrides it.
- Input eligibility is provider-neutral. OpenRouter adds no content classifier,
  secret-value embargo, held-section split, or payload-content fallback.
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
