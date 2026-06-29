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
/openrouter --model z-ai/glm-5.2 Summarize the security implications of this diff
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

Resolve the wrapper via the plugin cache (works from any CWD, including non-depot worktrees), then invoke it. Pipe via stdin for prompts containing code or special characters:

```bash
WRAPPER_PATH=""
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER_PATH=$(ls -t "$CACHE_ROOT"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER_PATH" ] && break
done
if [ -z "$WRAPPER_PATH" ] || [ ! -x "$WRAPPER_PATH" ]; then
  echo "openrouter wrapper not found in plugin cache" >&2
  exit 1
fi

RESULT=$(echo "${USER_PROMPT}" | OPENROUTER_ZDR=1 bash "$WRAPPER_PATH" "${MODEL}" - "${TIMEOUT}")
```

The wrapper JSON-encodes the prompt safely; never embed raw user input directly in a curl `-d` body.

### Step 5: Handle Errors

Exit codes: `0` success, `28` timeout, `1` exhausted/error, `2` bad args. On error, report the type to the user.

### Step 6: Present Response

The wrapper prints the model's text content directly -- `$RESULT` is the answer. Present it to the user. (Unlike `/deepseek`, there is no JSON envelope to parse.)
