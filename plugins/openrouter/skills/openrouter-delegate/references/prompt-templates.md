# Prompt Templates

Structured prompt patterns for each OpenRouter delegation type. Every prompt must be fully self-contained -- OpenRouter has no access to Claude's conversation context, MCP servers, or prior state.

## Principles

1. **Self-contained.** Include all context the task requires. OpenRouter starts fresh every invocation.
2. **Output format specified.** Tell the model exactly what structure to return.
3. **Constraints explicit.** If findings should be P1/P2/P3, define what each severity means.
4. **System via env, task via prompt.** The wrapper takes the system prompt from `OPENROUTER_SYSTEM`; the task content is the prompt argument (or stdin).

---

## Diff Analysis Template

For analyzing large diffs or preserving Codex subscription headroom.

**System prompt (`OPENROUTER_SYSTEM`):**
```
You are a senior code reviewer. Analyze diffs for security vulnerabilities, architectural violations, code quality issues, and potential bugs. Be precise: cite file paths and line numbers. Report only genuine issues, not style preferences.
```

**User prompt (prompt arg or stdin):**
```
Analyze this diff for a {PROJECT_TYPE} project.

Key conventions: {KEY_CONVENTIONS}

<diff>
{FULL_DIFF_CONTENT}
</diff>

Report findings using these severity levels:
- **P1 (Critical):** Security vulnerabilities, data loss risks, crashes. Must fix before merge.
- **P2 (Serious):** Logic errors, architectural violations, performance problems. Should fix.
- **P3 (Moderate):** Code style, naming issues, minor improvements. Fix if convenient.

For each finding:
- **File:** path/to/file
- **Line:** line number or range
- **Severity:** P1/P2/P3
- **Category:** security | architecture | logic | performance | style
- **Description:** What the issue is and why it matters
- **Suggestion:** How to fix it

If no issues found, state "No issues found" explicitly.
Focus on changed code only. Do not flag pre-existing issues in context lines.
```

**Model:** `z-ai/glm-5.2` (default), `deepseek/deepseek-v4-pro` fallback. **Timeout:** 120s (<10K lines) / 180s (>=10K lines).

---

## Direct Delegation Template

For the `/openrouter` command -- general-purpose delegation.

**User prompt:**
```
{USER_PROMPT}

Respond concisely and directly.
```

**Model:** `z-ai/glm-5.2` unless the user passes `--model`. **Timeout:** 90s.

---

## Config / Doc Generation Template

For one-shot text the caller writes to disk (valid wrapper use; not agentic implementation).

**System prompt (`OPENROUTER_SYSTEM`):**
```
You are a precise technical writer. Output only the requested file content with no commentary, no code fences, and no preamble.
```

**User prompt:**
```
Generate the contents of {TARGET_FILE} for a {PROJECT_TYPE} project.

Requirements:
{REQUIREMENTS}

Output only the file content.
```

**Model:** `z-ai/glm-5.2`. **Timeout:** 90s. The orchestrator writes the returned text to `{TARGET_FILE}` and commits it -- the wrapper never touches the filesystem.

---

## Output Parsing

The wrapper prints the model's text content directly (it already extracts `.choices[0].message.content`). There is no JSON envelope to parse -- capture stdout as the answer:

```bash
RESULT=$(bash "$WRAPPER_PATH" "z-ai/glm-5.2" "$PROMPT" 120 "deepseek/deepseek-v4-pro")
# $RESULT is the model's text directly
```
