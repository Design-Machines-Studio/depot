---
name: openrouter
description: Direct OpenRouter invocation with model selection. Delegates a prompt to an OpenRouter model and returns the response. Uses Terra by default with Kimi K3 as the quality fallback.
argument-hint: "<prompt> [--model <slug>]"
---

# /openrouter

Delegate a prompt directly to an OpenRouter model in one pass on a trusted
developer workstation.

## Usage

```
/openrouter Review this function for potential race conditions
/openrouter --model moonshotai/kimi-k3 Perform an adversarial security review
/openrouter --model deepseek/deepseek-v4-pro Analyze the architectural coupling between these modules
/openrouter --model z-ai/glm-5.2 Find duplicated validation patterns in this diff
```

An OpenRouter security result is a preliminary external lens. Consequential
security completion still requires a full-input reviewer from a family other
than the implementation family.

## Process

### Step 1: Parse Arguments

Extract the prompt and optional `--model` flag from the user's input.

- If `--model` is specified, use that slug exactly.
- Otherwise use `openai/gpt-5.6-terra` with `moonshotai/kimi-k3` as fallback.
- Reject any primary or fallback slug beginning with `anthropic/`; Anthropic
  remains native-Claude-only.

### Step 2: Check Prerequisites

Either `OPENROUTER_API_KEY` or `OPENROUTER_API_KEY_FILE` authorizes this
configured-key development path. The wrapper validates the file form as a
non-symlink regular file owned by the current UID with mode 0600. If neither is
configured, report OpenRouter unavailable; do not ask for approval.

### Step 3: Select Timeout

Default to 3600s. Increase to 7200s for inputs at or above 10K lines. The
wrapper separately enforces connection, first-byte, and stream-idle timeouts.

### Step 4: Resolve, Screen, and Invoke Once

Resolve `WORKFLOW_KERNEL` once using the workflow-kernel runtime-resolution
contract. Select one coherent installed OpenRouter bundle and derive every
asset from that root:

```bash
: "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh first}"
ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && ACTIVE_HOST="codex"
resolve_openrouter_bundle() {
  if [ -n "$ACTIVE_HOST" ]; then
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 --active-host "$ACTIVE_HOST" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  fi
}
BUNDLE_JSON=$(resolve_openrouter_bundle) || exit 1
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
POLICY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"

PROMPT_FILE=$(mktemp)
SYSTEM_FILE=$(mktemp)
RECEIPT_FILE=$(mktemp)
trap 'rm -f "$PROMPT_FILE" "$SYSTEM_FILE" "$RECEIPT_FILE"' EXIT
printf '%s' "$USER_PROMPT" > "$PROMPT_FILE"
printf '%s' "${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}" > "$SYSTEM_FILE"

if ! "$BOUNDARY_PATH" --mode artifact-delegation --policy "$POLICY_PATH" \
    --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE" >/dev/null; then
  echo "OpenRouter disclosure declined; no prompt bytes were sent."
  exit 1
fi

RESULT=$(env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$SYSTEM_FILE" \
  OPENROUTER_WORKLOAD=direct OPENROUTER_RECEIPT_FILE="$RECEIPT_FILE" \
  bash "$WRAPPER_PATH" "$MODEL" - "$TIMEOUT" "${FALLBACK_MODEL:-}" < "$PROMPT_FILE")
```

This is a single-pass path with no user-approval state. Workflow Authority
presence or health has no bearing on configured-key availability.

The wrapper JSON-encodes the prompt into private temporary storage, streams the
response, and records a content-free receipt. The boundary refuses unmistakable
credentials, private keys, authenticated DSNs, access/session tokens, and
explicitly classified private or regulated material before provider contact.

### Step 5: Handle Errors

Wrapper statuses are `0` success, `28` timeout, `1` exhausted/provider/key
error, and `2` invalid arguments or a forbidden model origin. A boundary
decline or wrapper failure sends nothing further and does not trigger an
approval prompt. Report the content-free failure receipt when available.

### Step 6: Present Response and Receipt

Present the model text, followed by the content-free generation ID, response
model, serving provider and provenance, usage, and request-envelope digest from
the receipt. A null provider with `not_reported_by_completion` is not verified
provider identity. Never print temporary prompt/system files or receipt fields
containing prompt, response, API-key, or secret content.

Recommend provider-side per-key spending limits for runaway-cost control; do
not add a second local approval or billing service.
