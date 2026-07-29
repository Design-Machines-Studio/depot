# Invocation Protocol

Complete reference for invoking the OpenRouter API from Claude Code via the Bash tool, using `references/openrouter-wrapper.sh`.

## The Wrapper

`openrouter-wrapper.sh` is a single-turn completion runner with stable exit codes (`0` success, `28` timeout, `1` exhausted/error, `2` bad arguments). It uses positional arguments (`<model> <prompt|-> [timeout] [fallback]`) and centralizes provider preferences, rate-limit fallback, JSON body construction, response extraction, and timeout enforcement.

**Argument shape (positional):**

```
openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
```

- `<model-slug>` -- OpenRouter model ID, e.g. `moonshotai/kimi-k3` or `z-ai/glm-5.2`
- `<prompt|->` -- literal prompt string, or `-` to read the prompt from stdin (use for large diffs)
- `[timeout_s]` -- per-attempt timeout in seconds (default `90`)
- `[fallback-slug]` -- a second model to try if the primary returns HTTP 429/503

Both model arguments must be third-party OpenRouter slugs. `openai/*` and `anthropic/*` are rejected before network contact; use native Codex and Claude CLIs for those vendors.

**Output:** the wrapper prints the model's **text content directly** (it already extracts `.choices[0].message.content`). There is no JSON to parse -- stdout is the answer.

## Resolve the Wrapper Path

Resolve `WORKFLOW_KERNEL` once through workflow-kernel's runtime-resolution contract, request the complete asset set needed by the caller in one `resolve-plugin-bundle` call, and derive every asset from the returned root:

```bash
: "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh first}"
ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && ACTIVE_HOST="codex"
resolve_bundle() {
  if [ -n "$ACTIVE_HOST" ]; then
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.7.0 --active-host "$ACTIVE_HOST" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
      --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
      --required-asset skills/openrouter-delegate/references/mcp-control-plane.md
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.7.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
      --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
      --required-asset skills/openrouter-delegate/references/mcp-control-plane.md
  fi
}
BUNDLE_JSON=$(resolve_bundle)
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
SECURITY_POLICY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
AUTHORIZATION_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/payload-authorization.sh"
[ -x "$WRAPPER_PATH" ] && [ -r "$SECURITY_POLICY_PATH" ] &&
  [ -x "$BOUNDARY_PATH" ] && [ -x "$AUTHORIZATION_PATH" ] || exit 1
```

Persist only `version`, `cache_class`, and `reason` from the resolver receipt. `selected_root` is for immediate local use and must not enter public durable receipts.

## How to Invoke

Use the canonical `/openrouter` workflow, which applies the content boundary,
exact-payload user approval, unchanged-byte verification, and receipt handling
before it reaches this low-level wrapper:

```text
/openrouter --model moonshotai/kimi-k3 your prompt
/openrouter --model z-ai/glm-5.2 analyze this bounded mechanical change
```

The positional wrapper syntax above is an implementation interface, not an
authorization boundary. New callers must implement the full protocol in
Payload-Specific Host Authorization before invoking it.

## Environment Variables

- `OPENROUTER_API_KEY` (required): your OpenRouter API key. Never commit it.
- `OPENROUTER_SYSTEM` (default: terse coding assistant): system prompt.
- `OPENROUTER_BASE` (default `https://openrouter.ai/api/v1`): API base URL.
- `OPENROUTER_ZDR` (`1` to enable): restrict to providers that do **not** train on / retain data (`data_collection: deny`). Opt-in only -- privacy is demoted (Quality > Price > Speed > Provider privacy); set for genuinely sensitive material (client code under NDA, credentials-adjacent diffs).
- `OPENROUTER_REQUIRE_PARAMS` (default `1`): skip providers that do not support the requested params (keeps agentic calls from silently degrading).
- `OPENROUTER_PROVIDER_SORT` (`throughput|latency|price|exacto`): bias provider selection. Kimi defaults to `exacto` when neither sort nor order is supplied.
- `OPENROUTER_PROVIDER_ORDER`: optional comma-separated provider or exact endpoint slugs. When present, it overrides sort.
- `OPENROUTER_FALLBACK_PROVIDER_ORDER`: optional provider/endpoint order for a different fallback model. The primary order is never inherited across model identities.
- `OPENROUTER_ALLOW_FALLBACKS` (`0|1`, default `1`): whether an explicit provider order may fall through to other eligible providers.
- `OPENROUTER_RECEIPT_FILE`: optional path for a content-free JSON receipt containing generation ID, requested/attempted/response models, fallback use, serving-provider provenance, and usage. Prompt and completion content are never written to this receipt.

## Security Hardening

- API key is passed via the `Authorization` header, never in URLs or args visible to `ps`.
- The prompt is JSON-encoded via `jq` (`--arg`), preventing injection through shell/JSON metacharacters in user content.
- Provider preferences are sent per-request, not relied upon from dashboard defaults.
- Stable model aliases are used for routing; the response model in the receipt preserves the canonical dated model actually served.

For live catalog, provider, endpoint, benchmark, and credit inspection, use
`mcp-control-plane.md`. MCP telemetry is advisory; this direct response receipt
remains authoritative for the call because the MCP OAuth identity may not share
the direct API key's workspace.

## Payload-Specific Host Authorization

Every workflow requires user disclosure approval for the exact outbound
payload. Treat it as byte-bound authority, separate from network permission:

1. Run `delegation-boundary.sh` first and materialize the exact eligible system
   and user prompt bytes in private temporary files.
2. Run `payload-authorization.sh snapshot` over the ordered files and request
   approval for its content-free combined `payloadSha256`.
3. Immediately before transmission, run `payload-authorization.sh verify` with
   the user-approved digest and the same ordered files. Any mutation,
   reordering, or membership change requires fresh authorization.
4. Never retry around a denial or broaden a file-specific authorization. Record
   `host_disclosure_declined` and fall back to Codex.

### Codex network allowlist

For a trusted local Codex installation, the user may reduce repeated
network-execution approvals by enabling workspace-write networking and
allowlisting only the endpoint used by this wrapper:

```toml
[sandbox_workspace_write]
network_access = true

[features.network_proxy]
enabled = true
domains = { "openrouter.ai" = "allow" }
```

This controls whether sandboxed commands can reach OpenRouter. It does not
override payload-specific disclosure review, workspace policy, or a declined
boundary check.

## API Endpoint

```
POST https://openrouter.ai/api/v1/chat/completions
```

**Headers:** `Authorization: Bearer ${OPENROUTER_API_KEY}`, `Content-Type: application/json`.

**Request body (built by the wrapper):**

```json
{
  "model": "moonshotai/kimi-k3",
  "provider": { "require_parameters": true, "sort": "exacto" },
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ]
}
```

## Exit Codes & Error Handling

| Exit | Meaning | Action |
|------|---------|--------|
| `0` | Success | stdout is the model's text content. |
| `28` | Timeout | Report timeout, proceed without OpenRouter input. Do not retry. |
| `1` | Exhausted / error | Bad API response or non-recoverable HTTP. The wrapper prints `### RUNNER FAILURE ...` to stderr. Skip gracefully. |
| `2` | Bad args / origin rejection | Missing arguments or an `openai/*` / `anthropic/*` primary or fallback. |

Internally, HTTP 429/503 on the primary triggers the `[fallback-slug]` model if provided; if the fallback also fails, the wrapper returns `1`. Automated review runners convert failures into `### RUNNER FAILURE` so dm-review can retry the coding lane on Codex. Direct `/openrouter` calls report failure to the user.
