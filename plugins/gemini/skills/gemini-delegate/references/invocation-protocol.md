# Invocation Protocol

Complete reference for invoking Gemini CLI from Claude Code via the Bash tool.

## Fallback chain

The Gemini CLI does not auto-fall-back when a model returns HTTP 429. Earlier versions of this document claimed `pro → flash → flash-lite → skip` happens automatically; it does not. On 2026-04-22 Pro was rate-limited across 10 internal retries and exited with an error, while a manual rerun with `-m flash` succeeded in 23 seconds.

The fix is `references/gemini-wrapper.sh`, a small bash wrapper that walks the fallback chain in real life.

**Why it exists.** Replaces aspirational documentation with a working script. Captures stderr from each invocation, matches it against anchored rate-limit patterns (`\b429\b`, `exhausted your capacity`, `\bquota\b (exceeded|limit|exhaust)`, `\brate limit\b`, `\btoo many requests\b`), and only retries on the next model when the failure looks like a quota issue. Non-quota failures (auth, malformed prompt, network) abort and surface the original exit code. Word boundaries on `429` and contextual punctuation around `quota`/`rate limit` prevent the wrapper from silently downgrading the model when the words appear coincidentally in non-error stderr output.

**How to invoke.**

Resolve the wrapper path via the plugin cache so this works from any CWD (pipeline runs in worktrees outside the depot where depot-relative paths fail):

```bash
WRAPPER_PATH=$(ls -t ~/.claude/plugins/cache/depot/gemini/*/skills/gemini-delegate/references/gemini-wrapper.sh 2>/dev/null | head -1)
[ -n "$WRAPPER_PATH" ] && [ -f "$WRAPPER_PATH" ] || { echo "gemini wrapper not found in plugin cache" >&2; exit 1; }
```

Then use `$WRAPPER_PATH` for every invocation:

```bash
# Direct invocation (starts at pro, walks down on 429)
bash "$WRAPPER_PATH" -p "your prompt" --output-format json --raw-output

# Start at a specific model and walk down from there
bash "$WRAPPER_PATH" -m flash -p "your prompt" --output-format json --raw-output

# Source it and call the function
source "$WRAPPER_PATH"
gemini_with_fallback -p "your prompt" --output-format json --raw-output
```

The wrapper passes every argument other than `-m <model>` through to the `gemini` CLI verbatim, so existing flag conventions (`--output-format json`, `--raw-output`, `-p`, heredoc piping) keep working.

**Dependency.** The wrapper bounds run time with `gtimeout` from coreutils. Install once with `brew install coreutils`. If `gtimeout` is missing the wrapper exits 127 with a clear message.

**429 detection.** A failure counts as a rate-limit case when the underlying `gemini` exit was non-zero AND stderr matches the rate-limit regex above. Anything else is treated as a real failure and surfaced. This avoids burning through the chain on bugs that look nothing like quota errors.

**Exit behavior.** When all three models in the chain are rate-limited, the wrapper exits 1 with the message `all models in fallback chain exhausted; try again later`. It does NOT return success silently. Callers can branch on the exit code and decide whether to skip the Gemini-dependent step or surface the failure.

**Environment variables.**

- `GEMINI_TIMEOUT_S` (default `60`): per-attempt timeout in seconds.
- `GEMINI_YOLO` (default `1`): pass `--yolo` to gemini for automated flows. Set to `0` for sensitive contexts where you want gemini to pause for tool-use confirmation. The wrapper still runs; only the `--yolo` flag is omitted.

**Security hardening.**

- The wrapper resets `PATH` to a fixed value (`/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`) before invoking dependencies. Caller-controlled `PATH` cannot hijack `gemini`, `gtimeout`, `grep`, `cat`, `rm`, or `mktemp`. The caller's `PATH` is restored on return.
- Stderr from gemini is filtered through `tr` to strip ANSI escape sequences before forwarding to the user's terminal. This blocks OSC 52 clipboard hijack, OSC 8 phishing hyperlinks, and cursor manipulation that could land via crafted prompts reflected in gemini's error output.
- Temp files are created with 0600 permissions and cleaned up on every return path. When the wrapper runs as a script (not sourced), an `EXIT INT TERM` trap removes any leftover temp files. Sourced mode does not register the trap (it would fire on the caller's shell exit) and instead relies on per-iteration explicit cleanup.
- Sourced mode does not export `PATH` to the caller's shell; the function saves and restores `PATH` internally. Internal constants are prefixed `__GEMINI_WRAPPER_` to avoid namespace collisions.

## CLI Syntax

```
gemini -p "<prompt>" -m <model> --output-format json --raw-output
```

**Flags:**

| Flag | Purpose | Required |
|------|---------|----------|
| `-p "<prompt>"` | Non-interactive prompt (headless mode) | Yes (or use stdin/heredoc) |
| `-m <model>` | Model selection: `flash`, `pro`, `flash-lite` | Yes |
| `--output-format json` | Return structured JSON instead of text | Yes |
| `--raw-output` | Suppress interactive formatting | Recommended |
| `--yolo` | Bypass all interactive confirmation prompts | Recommended for automated flows |

**The `--yolo` flag** is critical for automated pipelines. Without it, Gemini may pause for tool-use confirmation (e.g., before executing `google_web_search`), breaking the automation loop. Always append `--yolo` when invoking from a subagent or pipeline. When using `gemini-wrapper.sh`, `--yolo` is on by default; set `GEMINI_YOLO=0` to opt out for sensitive contexts where you want the confirmation prompts.

**Always wrap with `timeout`** to prevent hanging:

```bash
timeout <seconds> gemini -p "..." -m flash --yolo --output-format json --raw-output 2>/dev/null
```

Redirect stderr (`2>/dev/null`) to suppress progress indicators and retry messages.

## Input Methods

### Short Prompts (Direct)

For prompts under ~1000 characters:

```bash
RESULT=$(timeout 60 gemini -p "Analyze this function for security issues: $(cat path/to/file.go)" -m flash --output-format json --raw-output 2>/dev/null)
```

### Large Inputs (Heredoc)

For diffs, file contents, or multi-file context:

```bash
RESULT=$(timeout 120 cat <<'GEMINI_INPUT' | gemini -m flash --yolo --output-format json --raw-output 2>/dev/null
<task>
Analyze this diff for security vulnerabilities, architectural violations, and code quality issues.
Return findings as a JSON array with fields: file, line, severity (P1/P2/P3), description.
</task>

<diff>
... full diff content ...
</diff>
GEMINI_INPUT
)
```

**Important:** Use quoted delimiter (`<<'GEMINI_INPUT'`) to prevent shell variable expansion within the heredoc. This is critical when the content contains `$`, backticks, or other shell metacharacters (common in code diffs).

### Stdin Piping

For piping existing command output:

```bash
git diff main...HEAD | timeout 120 gemini -p "Review this diff for issues. Return P1/P2/P3 findings as JSON." -m flash --output-format json --raw-output 2>/dev/null
```

**Note:** When using stdin piping, the prompt goes in `-p` and the piped content is additional context. Gemini receives both.

## Response Format

### Success Response

```json
{
  "session_id": "uuid",
  "response": "The actual text response from Gemini",
  "stats": {
    "models": {
      "gemini-3-flash-preview": {
        "api": { "totalRequests": 1, "totalErrors": 0, "totalLatencyMs": 2516 },
        "tokens": { "input": 8335, "candidates": 7, "total": 8399, "cached": 0 }
      }
    },
    "tools": {
      "totalCalls": 0,
      "byName": {}
    }
  }
}
```

**Extraction:** Parse `.response` for the actual content. Use `.stats.tools.byName` to verify which tools Gemini used (e.g., `google_web_search`).

### Error Response

```json
{
  "session_id": "uuid",
  "error": { "type": "Error", "message": "description", "code": 1 }
}
```

### Search-Grounded Response

When Gemini uses `google_web_search`, the stats reflect it:

```json
{
  "stats": {
    "tools": {
      "totalCalls": 1,
      "byName": {
        "google_web_search": { "count": 1, "success": 1, "durationMs": 12723 }
      }
    }
  }
}
```

The citations are embedded in the `response` text — Gemini formats them inline with source URLs.

## Error Handling Protocol

After every Gemini invocation, check these four failure modes in order:

### 1. Timeout (Exit Code 124)

```bash
RESULT=$(timeout 60 gemini -p "..." -m flash --output-format json --raw-output 2>/dev/null)
EXIT_CODE=$?
if [ $EXIT_CODE -eq 124 ]; then
  echo "Gemini timed out after 60s"
fi
```

**Action:** Report timeout, proceed without Gemini input. Do not retry — the timeout was chosen to match expected latency for the task type.

### 2. Rate Limit (RetryableQuotaError)

Check if the response contains an error with quota message:

```bash
if echo "$RESULT" | grep -q "exhausted your capacity"; then
  # Fall back to cheaper model
fi
```

**Action:** Use `references/gemini-wrapper.sh` to walk the fallback chain (`pro` → `flash` → `flash-lite`). The CLI does not auto-fall-back; the wrapper does. See the **Fallback chain** section at the top of this file for invocation, dependencies, and exit semantics. If all three models are exhausted the wrapper exits 1; surface that to the caller rather than skipping silently.

### 3. Empty Response

Check if `.response` field is missing or empty:

**Action:** Report: "Gemini returned empty response." Proceed without Gemini input.

### 4. Malformed JSON

If the output isn't parseable as JSON:

**Action:** Report: "Gemini returned unparseable output." Log the first 200 characters for debugging. Proceed without Gemini input.

## Shell Safety

- Always use `2>/dev/null` to suppress stderr (retry messages, progress bars)
- Always use quoted heredoc delimiters (`<<'EOF'`) for code content
- Always wrap with `timeout` to prevent hanging processes
- Never embed user input directly in the `-p` flag without escaping — use heredoc for untrusted content
- Check `$?` exit code before parsing output
