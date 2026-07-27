# Invocation Protocol

Complete reference for invoking the OpenRouter API from Claude Code via the Bash tool, using `references/openrouter-wrapper.sh`.

## The Wrapper

`openrouter-wrapper.sh` is a single-turn completion runner with stable exit codes (`0` success, `28` timeout, `1` exhausted/error, `2` bad arguments). It uses positional arguments (`<model> <prompt|-> [timeout] [fallback]`) and centralizes provider preferences, rate-limit fallback, JSON body construction, response extraction, and timeout enforcement.

**Argument shape (positional):**

```
openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
```

- `<model-slug>` -- OpenRouter model ID, e.g. `z-ai/glm-5.2` or `deepseek/deepseek-v4-pro`
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
      --minimum-version 1.6.0 --active-host "$ACTIVE_HOST" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.6.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  fi
}
BUNDLE_JSON=$(resolve_bundle)
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
SECURITY_POLICY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
[ -x "$WRAPPER_PATH" ] && [ -r "$SECURITY_POLICY_PATH" ] && [ -x "$BOUNDARY_PATH" ] || exit 1
```

Persist only `version`, `cache_class`, and `reason` from the resolver receipt. `selected_root` is for immediate local use and must not enter public durable receipts.

## How to Invoke

```bash
# GLM-5.2, explicit 120s timeout, DeepSeek V4 rate-limit fallback (wrapper default timeout is 90s)
bash "$WRAPPER_PATH" "z-ai/glm-5.2" "your prompt" 120 "deepseek/deepseek-v4-pro"

# Custom system prompt (env), opt-in ZDR, prompt via stdin (large content)
echo "large diff content" | OPENROUTER_ZDR=1 \
  OPENROUTER_SYSTEM="You are a senior code reviewer." \
  bash "$WRAPPER_PATH" "z-ai/glm-5.2" - 180 "deepseek/deepseek-v4-pro"
```

## Environment Variables

- `OPENROUTER_API_KEY` (required): your OpenRouter API key. Never commit it.
- `OPENROUTER_SYSTEM` (default: terse coding assistant): system prompt.
- `OPENROUTER_BASE` (default `https://openrouter.ai/api/v1`): API base URL.
- `OPENROUTER_ZDR` (`1` to enable): restrict to providers that do **not** train on / retain data (`data_collection: deny`). Opt-in only -- privacy is demoted (Quality > Price > Speed > Provider privacy); set for genuinely sensitive material (client code under NDA, credentials-adjacent diffs).
- `OPENROUTER_REQUIRE_PARAMS` (default `1`): skip providers that do not support the requested params (keeps agentic calls from silently degrading).
- `OPENROUTER_PROVIDER_SORT` (`throughput|latency|price`): bias provider selection.

## Security Hardening

- API key is passed via the `Authorization` header, never in URLs or args visible to `ps`.
- The prompt is JSON-encoded via `jq` (`--arg`), preventing injection through shell/JSON metacharacters in user content.
- Provider preferences are sent per-request, not relied upon from dashboard defaults.

## API Endpoint

```
POST https://openrouter.ai/api/v1/chat/completions
```

**Headers:** `Authorization: Bearer ${OPENROUTER_API_KEY}`, `Content-Type: application/json`.

**Request body (built by the wrapper):**

```json
{
  "model": "z-ai/glm-5.2",
  "provider": { "require_parameters": true, "data_collection": "deny" },
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
