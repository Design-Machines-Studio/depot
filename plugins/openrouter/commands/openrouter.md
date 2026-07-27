---
name: openrouter
description: Direct OpenRouter invocation with model selection. Delegates a prompt to an OpenRouter model and returns the response. Use for ad-hoc review/analysis or text generation that benefits from GLM-5.2's quality-per-dollar or 1M context at lower cost.
argument-hint: "<prompt> [--model <slug>]"
---

# /openrouter

Delegate a prompt directly to an OpenRouter model (single-turn completion).

## Usage

```
/openrouter Review this function for potential race conditions
/openrouter --model deepseek/deepseek-v4-pro Analyze the architectural coupling between these modules
/openrouter --model z-ai/glm-5.2 Find duplicated validation patterns in this diff
```

## Process

### Step 1: Parse Arguments

Extract the prompt and optional `--model` flag from the user's input.

- If `--model` is specified, use that slug.
- If `--model` is not specified, use the default `z-ai/glm-5.2`.

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
    --minimum-version 1.6.0 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --active-host "$ACTIVE_HOST")
else
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.6.0 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh)
fi
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) exit 1;; esac
WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
[ -x "$WRAPPER_PATH" ] || exit 1

RESULT=$(echo "${USER_PROMPT}" | bash "$WRAPPER_PATH" "${MODEL}" - "${TIMEOUT}")
```

The wrapper JSON-encodes the prompt safely; never embed raw user input directly in a curl `-d` body.
Models beginning with `openai/` or `anthropic/` are invalid on this command. Use the native Codex or Claude CLI instead.

### Step 5: Handle Errors

Exit codes: `0` success, `28` timeout, `1` exhausted/error, `2` bad args. On error, report the type to the user.

### Step 6: Present Response

The wrapper prints the model's text content directly -- `$RESULT` is the answer. Present it to the user; there is no JSON envelope to parse.
