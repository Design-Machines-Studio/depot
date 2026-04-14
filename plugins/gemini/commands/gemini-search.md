---
name: gemini-search
description: Search-grounded query returning cited results. Delegates a research query to Gemini CLI with Google search grounding and returns structured findings with source URLs.
argument-hint: "<query>"
---

# /gemini-search

Run a search-grounded query through Gemini and return cited results.

## Usage

```
/gemini-search Datastar SSE framework latest version and breaking changes
/gemini-search Go Templ v0.3 migration guide
/gemini-search WCAG 2.2 new success criteria for focus appearance
```

## Process

### Step 1: Construct Search Prompt

Wrap the user's query in the search grounding template:

```
Research the following topic and provide comprehensive, current information with cited sources.

<topic>
${USER_QUERY}
</topic>

Return your findings in this structure:

## Summary
2-3 sentence overview of what you found.

## Key Findings
For each finding:
- **Finding:** [what you learned]
- **Source:** [URL]
- **Relevance:** [why this matters]

## Sources
Numbered list of all URLs consulted.
```

### Step 2: Invoke Gemini

Always use `flash` model for search — best cost/quality tradeoff. Use heredoc to avoid shell injection from user query:

```bash
RESULT=$(timeout 60 cat <<'GEMINI_INPUT' | gemini -m flash --yolo --output-format json --raw-output 2>/dev/null
${SEARCH_PROMPT}
GEMINI_INPUT
)
```

### Step 3: Handle Errors

Check for the four failure modes. On failure, report to user and suggest using WebSearch as fallback.

### Step 4: Verify Search Was Used

Check `stats.tools.byName.google_web_search` in the response:

- If present: Results are search-grounded with real citations. Present with confidence.
- If absent: Gemini answered from training data. Note: "Gemini did not use web search for this query. Results may not reflect current state. Consider using WebSearch for verification."

### Step 5: Present Results

Format the `response` field as a clean research brief with cited sources prominently displayed. The user asked for search — citations are the primary value.
