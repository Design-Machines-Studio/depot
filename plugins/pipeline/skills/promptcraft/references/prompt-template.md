# Execution Prompt Template

Each generated prompt follows this structure. The goal is a self-contained document that a subagent can execute without needing to read the plan, research brief, or any external context.

## Template

```markdown
# Chunk: [Chunk Title]

## Context

[2-3 sentences explaining what this chunk is part of and why it matters. Include the feature name and how this chunk fits into the larger work.]

## Task

[Clear, imperative description of what to build or change. Be specific -- "Add a new handler for POST /api/proposals" not "implement the proposals API."]

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| path/to/file.go | Create | New handler file |
| path/to/existing.go | Modify | Add new route registration |
| path/to/template.templ | Create | New page template |

## Files to Read (for context)

| File | Why |
|------|-----|
| path/to/similar.go | Follow this handler's pattern |
| path/to/types.go | DTO definitions to reuse |

## Patterns to Follow

[Specific patterns extracted from the assessment. Include actual code snippets where helpful.]

- Handler pattern: [describe or show example]
- Error handling: [describe convention]
- Naming: [describe convention]

## Companion Skills

Load these skills for domain-specific guidance:
- [skill name] from [plugin] -- [what it helps with]

## Acceptance Criteria

- [ ] [Specific, testable criterion]
- [ ] [Another criterion]
- [ ] [Build/compile passes]
- [ ] [Tests pass (if applicable)]

## Constraints

- Only modify the files listed above
- Follow existing patterns -- do not introduce new abstractions
- Do not refactor surrounding code unless required for the task
- [Any additional constraints specific to this chunk]

## Research Context

[Relevant findings from the research brief, inlined here. Only include what's directly relevant to this chunk.]
```

## Guidelines for Writing Prompts

1. **Inline everything.** The subagent should never need to read another file to understand its task. If a pattern is important, show it in the prompt.

2. **Be specific about files.** Use exact paths, not descriptions. "Modify `internal/handler/proposal.go`" not "update the proposal handler."

3. **Show, don't tell.** If there's a pattern to follow, include a code snippet from an existing file rather than describing it abstractly.

4. **Acceptance criteria must be verifiable.** "Build passes" is verifiable. "Code is clean" is not. "All new functions have error handling" is verifiable.

5. **Scope tightly.** If a subagent touches files outside its scope, it risks conflicting with parallel chunks. Be explicit about boundaries.

6. **Include the "why."** Context helps the subagent make good judgment calls when the prompt doesn't cover every edge case.
