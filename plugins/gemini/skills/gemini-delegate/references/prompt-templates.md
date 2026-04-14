# Prompt Templates

Structured prompt patterns for each Gemini delegation type. Every prompt must be fully self-contained — Gemini has no access to Claude's conversation context, MCP servers, or prior state.

## Principles

1. **Self-contained.** Include all context the task requires. Gemini starts fresh every invocation.
2. **Output format specified.** Tell Gemini exactly what structure to return.
3. **No tool instructions.** Don't tell Gemini to "use Google search" — frame the task so it naturally reaches for the right tool.
4. **Constraints explicit.** If findings should be P1/P2/P3, define what each severity means.

---

## Search Grounding Template

For web research with cited sources.

```
Research the following topic and provide comprehensive, current information with cited sources.

<topic>
{TOPIC_DESCRIPTION}
</topic>

<context>
{WHY_THIS_MATTERS — project context, what we're building, what decisions this informs}
</context>

Return your findings in this structure:

## Summary
2-3 sentence overview of what you found.

## Key Findings
For each finding:
- **Finding:** [what you learned]
- **Source:** [URL]
- **Relevance:** [why this matters for the context above]

## Recommendations
Based on the research, what should we do? Be specific and actionable.

## Sources
Numbered list of all URLs consulted.
```

**Model:** `flash`
**Timeout:** 60s

---

## Diff Analysis Template

For analyzing diffs that exceed Claude's truncation threshold.

```
You are a senior code reviewer. Analyze this diff for security vulnerabilities, architectural violations, code quality issues, and potential bugs.

<project-context>
{PROJECT_TYPE — e.g., "Go+Templ+Datastar web application", "Craft CMS Twig templates"}
{KEY_CONVENTIONS — e.g., "Uses Live Wires CSS framework", "Docker-based development"}
</project-context>

<diff>
{FULL_DIFF_CONTENT}
</diff>

Report findings using these severity levels:
- **P1 (Critical):** Security vulnerabilities, data loss risks, crashes. Must fix before merge.
- **P2 (Serious):** Logic errors, architectural violations, performance problems. Should fix before merge.
- **P3 (Moderate):** Code style, naming issues, minor improvements. Fix if convenient.

For each finding, provide:
- **File:** path/to/file
- **Line:** line number (or range)
- **Severity:** P1/P2/P3
- **Category:** security | architecture | logic | performance | style
- **Description:** What the issue is and why it matters
- **Suggestion:** How to fix it

If no issues found, state "No issues found" explicitly.

Focus on issues that are specific to the changed code. Do not flag pre-existing issues in unchanged context lines.
```

**Model:** `flash` for diffs <10K lines, `pro` for diffs >10K lines
**Timeout:** 60s / 180s

---

## Code Execution Template

For verifying algorithms, math, or data transformations using Gemini's Python sandbox.

```
Verify the correctness of this code by writing and executing a Python test.

<code-under-test>
{THE_FUNCTION_OR_ALGORITHM — in its original language}
</code-under-test>

<expected-behavior>
{WHAT_THE_CODE_SHOULD_DO — inputs, outputs, edge cases}
</expected-behavior>

Write a Python script that:
1. Reimplements the logic (or tests it directly if Python-compatible)
2. Tests it against the expected behavior with at least 5 test cases including edge cases
3. Prints PASS or FAIL for each test case
4. Prints a summary: "X/Y tests passed"

Execute the script and report:
- Whether all tests passed
- Any failing test cases with expected vs actual output
- Any edge cases that weren't covered in the expected behavior description
```

**Model:** `flash`
**Timeout:** 30s

---

## Direct Delegation Template

For `/gemini` command — general-purpose delegation.

```
{USER_PROMPT}

Respond concisely and directly. If the task benefits from web search, use it and cite sources. If the task benefits from code execution, write and run the code.
```

**Model:** Auto-selected based on prompt length:
- <500 chars: `flash-lite`
- 500-5000 chars: `flash`
- >5000 chars: `pro`

**Timeout:** Based on model selection (see model-selection.md)

---

## Template Usage Notes

### Escaping Content

When injecting code or diffs into templates, always use heredoc with quoted delimiter:

```bash
cat <<'GEMINI_INPUT' | gemini -m flash --output-format json --raw-output 2>/dev/null
... template with $variables and `backticks` safely preserved ...
GEMINI_INPUT
```

### Context Injection

When delegating from within a larger workflow (dm-review, pipeline research), inject the relevant context into the template. Gemini cannot look up project conventions or read local files — everything it needs must be in the prompt.

### Output Parsing

For structured outputs (diff analysis findings, search results), parse the `response` field as markdown. The templates request specific markdown structures that can be regex-parsed or section-split for integration into Claude's workflow.
