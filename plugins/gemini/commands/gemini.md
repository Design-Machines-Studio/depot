---
name: gemini
description: Direct Gemini invocation with model selection. Delegates a prompt to Gemini CLI and returns the response. Use for ad-hoc tasks that benefit from Gemini's search grounding, large context, or code execution.
argument-hint: "<prompt> [--model flash|pro|flash-lite]"
---

# /gemini

Delegate a prompt directly to Gemini CLI.

## Usage

```
/gemini What are the current best practices for Datastar SSE performance?
/gemini --model pro Analyze this complex architectural decision...
/gemini --model flash-lite What version of Go is latest?
```

## Process

### Step 1: Parse Arguments

Extract the prompt and optional `--model` flag from the user's input.

- If `--model` is specified, use that model
- If `--model` is not specified, auto-select based on prompt length:
  - <500 characters: `flash-lite` (fast factual lookup)
  - 500-5000 characters: `flash` (balanced)
  - >5000 characters: `pro` (deep reasoning)

### Step 2: Select Timeout

Based on model:
- `flash-lite`: 10s
- `flash`: 60s
- `pro`: 180s

### Step 3: Invoke Gemini

Use heredoc to avoid shell injection from user input:

```bash
RESULT=$(timeout ${TIMEOUT} cat <<'GEMINI_INPUT' | gemini -m ${MODEL} --yolo --output-format json --raw-output 2>/dev/null
${USER_PROMPT}
GEMINI_INPUT
)
```

Never use `-p "${USER_PROMPT}"` — user input may contain shell metacharacters (`$(...)`, backticks, double-quotes) that break out of quoting. Always use the heredoc pattern with a quoted delimiter.

### Step 4: Handle Errors

Check for the four failure modes (timeout, rate limit, empty, malformed).

On rate limit, fall back through the model chain: `pro` → `flash` → `flash-lite` → report failure.

On other failures, report the error type to the user.

### Step 5: Present Response

Extract the `response` field from Gemini's JSON output and present it to the user.

If Gemini used `google_web_search` (check `stats.tools.byName`), note: "Sources cited via Google search grounding."

If Gemini ran code (check for code execution in stats), note: "Code executed in Gemini's Python sandbox."
