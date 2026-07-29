---
name: openrouter
description: Direct OpenRouter invocation with model selection. Delegates a prompt to an OpenRouter model and returns the response. Uses Kimi K3 as the quality-first default with GLM-5.2 capacity fallback.
argument-hint: "<prompt> [--model <slug>]"
---

# /openrouter

Delegate a prompt directly to an OpenRouter model (single-turn completion).

## Usage

```
/openrouter Review this function for potential race conditions
/openrouter --model moonshotai/kimi-k3 Perform an adversarial security review
/openrouter --model deepseek/deepseek-v4-pro Analyze the architectural coupling between these modules
/openrouter --model z-ai/glm-5.2 Find duplicated validation patterns in this diff
```

An OpenRouter security result is a preliminary external lens. Consequential
security completion still requires a separate full-input Codex review.

## Process

### Step 1: Parse Arguments

Extract the prompt and optional `--model` flag from the user's input.

- If `--model` is specified, use that slug.
- If `--model` is not specified, use `moonshotai/kimi-k3` with `z-ai/glm-5.2` as the capacity fallback.
- If `--model` is specified, honor it exactly; do not silently replace an explicit user choice.

### Step 2: Check Prerequisites

Verify `OPENROUTER_API_KEY` is set:

```bash
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "OPENROUTER_API_KEY not set. Export it before using /openrouter."
  exit 1
fi
```

### Step 3: Select Timeout

Default 90s. Increase to 120-180s for large inputs (big diffs).

### Step 4: Invoke OpenRouter

Resolve `WORKFLOW_KERNEL` once using the workflow-kernel runtime-resolution contract. Then select one coherent installed OpenRouter bundle and derive the wrapper from it. Pipe prompts containing code or special characters through stdin:

```bash
: "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh first}"
ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && ACTIVE_HOST="codex"
if [ -n "$ACTIVE_HOST" ]; then
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.7.0 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
    --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
    --required-asset skills/openrouter-delegate/references/mcp-control-plane.md \
    --active-host "$ACTIVE_HOST")
else
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.7.0 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
    --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
    --required-asset skills/openrouter-delegate/references/mcp-control-plane.md)
fi
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
SECURITY_POLICY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
AUTHORIZATION_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/payload-authorization.sh"
[ -x "$WRAPPER_PATH" ] && [ -r "$SECURITY_POLICY_PATH" ] &&
  [ -x "$BOUNDARY_PATH" ] && [ -x "$AUTHORIZATION_PATH" ] || exit 1

PROMPT_FILE=$(mktemp)
SYSTEM_FILE=$(mktemp)
RECEIPT_FILE=$(mktemp)
AUTHORIZATION_FILE=$(mktemp)
trap 'rm -f "$PROMPT_FILE" "$SYSTEM_FILE" "$RECEIPT_FILE" "$AUTHORIZATION_FILE"' EXIT
printf '%s' "$USER_PROMPT" > "$PROMPT_FILE"
printf '%s' "${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}" > "$SYSTEM_FILE"
if ! "$BOUNDARY_PATH" --mode artifact-delegation \
    --policy "$SECURITY_POLICY_PATH" \
    --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE"; then
  echo "OpenRouter disclosure declined; no prompt bytes were sent."
  exit 1
fi

PAYLOAD_SHA256=$("$AUTHORIZATION_PATH" snapshot \
  --output "$AUTHORIZATION_FILE" \
  --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE")
```

Ask the user to approve disclosure of the exact payload identified by
`PAYLOAD_SHA256`; only the user can provide this authorization. Set
`approved_payload_sha256` from that response. A general permission statement,
the assistant's judgment, or a prior approval is not sufficient. Immediately
before calling the wrapper:

```bash
"$AUTHORIZATION_PATH" verify --manifest "$AUTHORIZATION_FILE" \
  --approved-sha256 "$approved_payload_sha256" \
  --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE"

RESULT=$(OPENROUTER_SYSTEM="$(cat "$SYSTEM_FILE")" \
  OPENROUTER_RECEIPT_FILE="$RECEIPT_FILE" \
  bash "$WRAPPER_PATH" "${MODEL}" - "${TIMEOUT}" "${FALLBACK_MODEL:-}" < "$PROMPT_FILE")
```

The wrapper JSON-encodes the prompt safely; never embed raw user input directly in a curl `-d` body.
Models beginning with `openai/` or `anthropic/` are invalid on this command. Use the native Codex or Claude CLI instead.
Payload-specific user authorization is mandatory; see
`references/invocation-protocol.md`.

### Step 5: Handle Errors

Exit codes: `0` success, `28` timeout, `1` exhausted/error, `2` bad args. On error, report the type to the user.

### Step 6: Present Response and Receipt

The wrapper prints the model's text content directly -- `$RESULT` is the
answer. Present it to the user, followed by the content-free generation ID,
canonical response model, serving provider and its provenance, and usage from
`$RECEIPT_FILE`. A null provider with
`not_reported_by_completion` means OpenRouter did not include that optional
field; it is not a verified provider identity. Never print the prompt from the
temporary file.

For live model/endpoint discovery, use the optional official MCP described in
`references/mcp-control-plane.md`. The direct runner and its team API key remain
authoritative for this call.
