# Invocation Protocol

Complete reference for invoking the OpenRouter API from Claude Code via the Bash tool, using `references/openrouter-wrapper.sh`.

## The Wrapper

`openrouter-wrapper.sh` is a streamed single-turn completion runner with stable
exit codes (`0` success, `28` timeout, `1` exhausted/error, `2` bad arguments).
It uses positional arguments (`<model> <prompt|-> [timeout] [fallback]`) and
centralizes provider preferences, native model fallback, private request-body
construction, stream assembly, provenance validation, and layered timeout
enforcement.

**Argument shape (positional):**

```
openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
```

- `<model-slug>` -- OpenRouter model ID, e.g. `moonshotai/kimi-k3` or `z-ai/glm-5.2`
- `<prompt|->` -- literal prompt string, or `-` to read the prompt from stdin (use for large diffs)
- `[timeout_s]` -- overall streamed completion budget in seconds (default
  `3600`; use `7200` for very large or bulk review)
- `[fallback-slug]` -- a second model included in the same ordered OpenRouter
  `models` request

Both model arguments must be valid OpenRouter slugs. `openai/*` is allowed on
the API fallback rail; `anthropic/*` is rejected before network contact and
remains native Claude-only.

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
      --minimum-version 1.14.0 --active-host "$ACTIVE_HOST" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
      --required-asset skills/openrouter-delegate/references/mcp-control-plane.md
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
      --required-asset skills/openrouter-delegate/references/mcp-control-plane.md
  fi
}
BUNDLE_JSON=$(resolve_bundle)
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
SECURITY_POLICY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
[ -x "$WRAPPER_PATH" ] && [ -r "$SECURITY_POLICY_PATH" ] &&
  [ -x "$BOUNDARY_PATH" ] || exit 1
```

Persist only `version`, `cache_class`, and `reason` from the resolver receipt. `selected_root` is for immediate local use and must not enter public durable receipts.

## How to Invoke

Use the canonical `/openrouter` workflow, which applies the automatic content
boundary and receipt handling
before it reaches this low-level wrapper:

```text
/openrouter --model moonshotai/kimi-k3 your prompt
/openrouter --model z-ai/glm-5.2 analyze this bounded mechanical change
```

The positional wrapper syntax above is an implementation interface, not an
authorization boundary. New callers must implement the full configured-key
protocol below before invoking it.

## Environment Variables

- `OPENROUTER_API_KEY`: your OpenRouter API key. Never commit it. Mutually
  exclusive with `OPENROUTER_API_KEY_FILE`.
- `OPENROUTER_API_KEY_FILE`: preferred for non-interactive harnesses. The
  wrapper accepts only a non-symlink regular file owned by the current UID with
  mode 0600 and a single non-empty UTF-8 line.
- `OPENROUTER_SYSTEM` (default: terse coding assistant): inline system prompt.
- `OPENROUTER_SYSTEM_FILE`: readable regular file containing the exact system
  prompt bytes. It is mutually exclusive with `OPENROUTER_SYSTEM`; authorized
  file-based callers must unset the inherited inline variable.
- `OPENROUTER_BASE`: production is pinned to
  `https://openrouter.ai/api/v1`. Overrides are test-only: the API key must be
  exactly `test` and the URL must be controlled loopback HTTP on `127.0.0.1`
  or `localhost` with an explicit port.
- `OPENROUTER_ZDR` (`1` to enable): restrict to providers that do **not** train on / retain data (`data_collection: deny`). Opt-in only -- privacy is demoted (Quality > Price > Speed > Provider privacy); set for genuinely sensitive material (client code under NDA, credentials-adjacent diffs).
- `OPENROUTER_WORKLOAD` (`quality|security|direct|bulk|mechanical`, default
  `quality`): selects the default routing strategy. Direct, bulk, and mechanical
  requests prefer throughput; quality and security Kimi requests prefer Exacto.
- `OPENROUTER_REQUIRE_PARAMS` (default `1`): skip providers that do not support the requested params (keeps agentic calls from silently degrading).
- `OPENROUTER_PROVIDER_SORT` (`throughput|latency|price|exacto`): explicitly
  override workload routing.
- `OPENROUTER_PROVIDER_ORDER`: optional comma-separated provider or exact endpoint slugs. When present, it overrides sort.
- `OPENROUTER_FALLBACK_PROVIDER_ORDER`: optional provider/endpoint slugs appended
  to the request order for the fallback model.
- `OPENROUTER_ALLOW_FALLBACKS` (`0|1`, default `1`): whether routing may fall
  through to other eligible providers.
- `OPENROUTER_OVERALL_TIMEOUT` (default `3600`): overall streamed completion
  budget when the positional timeout is omitted.
- `OPENROUTER_CONNECT_TIMEOUT` (default `30`): TCP/TLS connection timeout.
- `OPENROUTER_FIRST_BYTE_TIMEOUT` (default `600`): maximum time before the first
  streamed response byte.
- `OPENROUTER_IDLE_TIMEOUT` (default `600`): maximum time without stream
  progress. Any streamed bytes reset this watchdog; only a completed, validated
  stream becomes review evidence.
- `OPENROUTER_RECEIPT_FILE`: optional path for a content-free JSON success or
  failure receipt. Failure receipts record timeout/error classification without
  prompt, partial completion, inferred provider, or usage content.

## Security Hardening

- API key is passed via the `Authorization` header, never in URLs or args visible to `ps`.
- The prompt is JSON-encoded via `jq` (`--arg`), preventing injection through shell/JSON metacharacters in user content.
- Provider preferences are sent per-request, not relied upon from dashboard defaults.
- Stable model aliases are used for routing; the response model in the receipt preserves the canonical dated model actually served.

For live catalog, provider, endpoint, benchmark, and credit inspection, use
`mcp-control-plane.md`. MCP telemetry is advisory; this direct response receipt
remains authoritative for the call because the MCP OAuth identity may not share
the direct API key's workspace.

## Configured-Key Authorization

On a trusted developer workstation, either supported key input authorizes an
eligible payload. Direct `/openrouter`, dm-review, and the bounded Pipeline lane
all use one pass:

1. Resolve one coherent installed bundle and materialize the exact system/user
   files.
2. Run `delegation-boundary.sh --mode artifact-delegation` with the installed
   disclosure policy over those private files immediately before wrapper
   invocation.
3. On an automatic decline, contact no provider and fall back to Codex where a
   native fallback exists. Otherwise invoke the wrapper with those same private
   files.

No OpenRouter caller asks for user approval. Workflow Authority presence or
status has no effect. Provider-side per-key spending limits are the recommended
runaway-cost control.

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
override the automatic disclosure boundary, workspace policy, or a declined
boundary check.

## API Endpoint

```
POST https://openrouter.ai/api/v1/chat/completions
```

**Headers:** `Authorization: Bearer ${OPENROUTER_API_KEY}`, `Content-Type: application/json`.

**Request body with a fallback (built by the wrapper):**

```json
{
  "models": ["moonshotai/kimi-k3", "openai/gpt-5.6-terra"],
  "provider": {
    "require_parameters": true,
    "allow_fallbacks": true,
    "sort": "throughput"
  },
  "stream": true,
  "stream_options": {"include_usage": true},
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
| `28` | Timeout | Report the first-byte, idle, or overall timeout from the failure receipt; proceed without OpenRouter input. Do not issue a blind client retry. |
| `1` | Exhausted / error | Bad API response or non-recoverable HTTP. The wrapper prints `### RUNNER FAILURE ...` to stderr. Skip gracefully. |
| `2` | Bad args / origin rejection | Missing arguments or an `anthropic/*` primary or fallback. |

When a fallback is present, OpenRouter receives both models in one ordered
request and handles eligible fallback errors server-side. The wrapper never
blindly resubmits a timed-out generation. Automated review runners convert
failures into `### RUNNER FAILURE` so dm-review can retry the coding lane on
Codex. Direct `/openrouter` calls report the content-free failure receipt.
