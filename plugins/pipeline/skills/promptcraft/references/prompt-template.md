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

## Visual References (UI chunks only)

[If the brainstorm or design spec produced visual mockups, summarize the key decisions here. Omit this section entirely for non-UI chunks.]

Approved design: [path to brainstorm.md or mockup file]

Key visual decisions:
- [Decision 1: e.g., "Sidebar headings use h4 with font-medium, not h3"]
- [Decision 2: e.g., "Block/Abstain buttons use button--outline-danger, visually smaller than position buttons"]
- [Decision 3: e.g., "Natural-width buttons, not full-width"]

The rendered result must match these visual treatments. If you cannot determine the visual intent from these descriptions, read the mockup file at the path above.

## Acceptance Criteria

- [ ] [Specific, testable structural criterion]
- [ ] [Another structural criterion]
- [ ] [Build/compile passes]
- [ ] [Tests pass (if applicable)]

### Visual Acceptance Criteria (UI chunks only)

[Omit this subsection for non-UI chunks.]

- [ ] [Visual outcome criterion -- describes what it should LOOK like, not just what class to use]
- [ ] [E.g., "Block and Abstain buttons are visually lighter and smaller than position buttons"]
- [ ] [E.g., "Sidebar headings create a clear hierarchy -- h4 muted style, not competing with page heading"]

Visual criteria describe the IMPRESSION, not the implementation. "Uses button--outline-danger" is structural. "Block button is visually subordinate to the Accept button" is visual. Include both types.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` Sprint Contract Negotiation (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify the files listed above
- Follow existing patterns -- do not introduce new abstractions
- Do not refactor surrounding code unless required for the task
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
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

7. **Visual criteria are separate from structural criteria.** Structural: "button uses `.button--outline-danger` class." Visual: "button appears lighter and smaller than the primary action buttons." Both are needed for UI work. A subagent can satisfy the structural criterion (correct class) while failing the visual criterion (the class renders differently than expected in context).

8. **Reference the approved design.** When a brainstorm produced mockups, the prompt must reference them. The subagent can read HTML source even if it can't view rendered images. Include the path and the key visual decisions extracted from it.

9. **The Ambiguity Protocol and the last two Constraints bullets are invariant.** Copy them verbatim into every prompt. They close the seam between plan-adversary (structural ambiguity) and brainstorming (pre-plan ambiguity) by addressing implementation-time micro-decisions and drive-by refactors. Do not rewrite or shorten them per chunk.
