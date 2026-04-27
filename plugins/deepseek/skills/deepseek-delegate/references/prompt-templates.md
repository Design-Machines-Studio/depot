# Prompt Templates

Structured prompt patterns for each DeepSeek delegation type. Every prompt must be fully self-contained -- DeepSeek has no access to Claude's conversation context, MCP servers, or prior state.

## Principles

1. **Self-contained.** Include all context the task requires. DeepSeek starts fresh every invocation.
2. **Output format specified.** Tell DeepSeek exactly what structure to return.
3. **Constraints explicit.** If findings should be P1/P2/P3, define what each severity means.
4. **OpenAI message format.** DeepSeek uses the OpenAI chat completions API. System prompts go in the system role; task content goes in the user role.

---

## Diff Analysis Template

For analyzing diffs that exceed Claude's truncation threshold or to offload from Anthropic quota.

**System prompt:**
```
You are a senior code reviewer. Analyze diffs for security vulnerabilities, architectural violations, code quality issues, and potential bugs. Be precise: cite file paths and line numbers. Report only genuine issues, not style preferences.
```

**User prompt:**
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

**Model:** `v4-flash` for diffs <10K lines, `v4-pro` for diffs >10K lines
**Timeout:** 60s / 180s

---

## Code Analysis Template

For reviewing code patterns, suggesting refactorings, or analyzing architecture.

**System prompt:**
```
You are a code analyst specializing in {STACK_DESCRIPTION}. Provide specific, actionable analysis with file:line citations. Be concise.
```

**User prompt:**
```
{ANALYSIS_TASK}

<code>
{CODE_CONTENT}
</code>

{SPECIFIC_QUESTIONS_OR_CRITERIA}
```

**Model:** `v4-pro`
**Timeout:** 60s

---

## Direct Delegation Template

For `/deepseek` command -- general-purpose delegation.

**User prompt:**
```
{USER_PROMPT}

Respond concisely and directly.
```

**Model:** Auto-selected based on prompt length:
- <500 chars: `v4-flash`
- >=500 chars: `v4-pro`

**Timeout:** Based on model selection (see model-selection.md)

---

## Template Usage Notes

### JSON Escaping

The wrapper script handles JSON escaping via python3. For manual invocations:

```bash
# Safe: wrapper handles escaping
bash deepseek-wrapper.sh -p "prompt with $special chars"

# For stdin piping of large content:
cat large-file.txt | bash deepseek-wrapper.sh -s "system prompt" 
```

### Output Parsing

DeepSeek returns OpenAI-compatible JSON. Extract the response content:

```bash
echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

### Context Injection

When delegating from within a larger workflow (dm-review, pipeline), inject the relevant context into the template. DeepSeek cannot look up project conventions or read local files -- everything it needs must be in the prompt.
