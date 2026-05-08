---
name: deepseek
description: Direct DeepSeek V4 invocation with model selection. Delegates a prompt to DeepSeek API and returns the response. Use for ad-hoc tasks that benefit from Sonnet-class reasoning at lower cost.
argument-hint: "<prompt> [--model v4-pro|v4-flash]"
---

# /deepseek

Delegate a prompt directly to DeepSeek V4 API.

## Usage

```
/deepseek Review this function for potential race conditions
/deepseek --model v4-pro Analyze the architectural coupling between these modules
/deepseek --model v4-flash Check if this migration has the correct column types
```

## Process

### Step 1: Parse Arguments

Extract the prompt and optional `--model` flag from the user's input.

- If `--model` is specified, use that model
- If `--model` is not specified, auto-select based on prompt length:
  - <500 characters: `v4-flash` (fast, mechanical check)
  - >=500 characters: `v4-pro` (deep reasoning)

### Step 2: Check Prerequisites

Verify `DEEPSEEK_API_KEY` is set:

```bash
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "DEEPSEEK_API_KEY not set. Export it before using /deepseek."
  exit 1
fi
```

### Step 3: Select Timeout

Based on model:
- `v4-flash`: 60s
- `v4-pro`: 120s

### Step 4: Invoke DeepSeek

Resolve the wrapper script via the plugin cache (works from any CWD, including non-depot worktrees), then invoke it with the user's prompt:

```bash
WRAPPER_PATH=""
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER_PATH=$(ls -t "$CACHE_ROOT"/deepseek/*/skills/deepseek-delegate/references/deepseek-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER_PATH" ] && break
done
if [ -z "$WRAPPER_PATH" ] || [ ! -x "$WRAPPER_PATH" ]; then
  echo "deepseek wrapper not found in plugin cache" >&2
  exit 1
fi

RESULT=$(DEEPSEEK_TIMEOUT_S=${TIMEOUT} bash "$WRAPPER_PATH" \
  -m ${MODEL} \
  -p "${USER_PROMPT}")
```

For prompts containing code or special characters, pipe via stdin:

```bash
RESULT=$(echo "${USER_PROMPT}" | DEEPSEEK_TIMEOUT_S=${TIMEOUT} bash "$WRAPPER_PATH" \
  -m ${MODEL})
```

The wrapper handles JSON escaping via python3. Never embed raw user input directly in curl `-d`.

### Step 5: Handle Errors

Check for the four failure modes (timeout, rate limit, empty, malformed).

On rate limit, the wrapper automatically walks the fallback chain: `v4-pro` -> `v4-flash` -> report failure.

On other failures, report the error type to the user.

### Step 6: Present Response

Extract content from the OpenAI-compatible JSON response:

```bash
CONTENT=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])")
```

Present the content to the user. Include token usage for cost awareness:

```bash
TOKENS=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"({d['usage']['prompt_tokens']} in / {d['usage']['completion_tokens']} out tokens)\")")
```
