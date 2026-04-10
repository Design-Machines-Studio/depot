---
name: promptcraft
description: Takes a plan and generates self-contained execution prompts with overlap-aware dependency ordering and manifest. Use when breaking a plan into executable chunks for autonomous worktree-based execution. Invoke with /pipeline-prompts or as part of /pipeline. Analyzes file paths to determine parallel vs sequential execution strategy.
---

# Execution Prompt Generator

Transform a plan into self-contained execution prompts with overlap-aware dependency ordering. Produces a manifest that the execution-orchestrator consumes directly.

## Input

1. **Plan file** -- A markdown plan (from `/workflows:plan`, superpowers writing-plans, or hand-written)
2. **Original prompt** -- The user's verbatim input saved at `plans/<feature-slug>/original-prompt.md` with extracted Key Requirements
3. **Research Brief** (optional) -- Output from the research skill
4. **Assessment Brief** (optional) -- Output from the assess skill

## Process

### Phase 1: Plan Decomposition

Read the plan and identify discrete chunks of work. A chunk is:
- A logically complete unit (one feature aspect, one migration, one component)
- Implementable without needing to see intermediate results of other chunks
- Testable in isolation (has its own acceptance criteria)

**Decomposition rules:**
1. Database/schema changes are always their own chunk and always run first
2. Backend and frontend work on different files can be separate parallel chunks
3. Integration work (wiring things together) depends on the pieces it connects
4. Test-only chunks are rare -- tests should live with their implementation chunk
5. Configuration/deployment chunks run last

### Phase 2: Context Extraction

For each chunk, extract from the plan, research brief, and assessment brief:

1. **What to build** -- The specific deliverable
2. **File paths** -- Every file the chunk will read or modify
3. **Patterns to follow** -- Existing code patterns from the assessment
4. **References** -- Relevant research findings
5. **Acceptance criteria** -- How to know the chunk is done
6. **Companion skills** -- Which domain plugins to load (assembly, live-wires, etc.)

Read `references/prompt-template.md` for the exact prompt structure.

### Phase 2.5: Visual Reference Extraction

For UI chunks (those touching `.templ`, `.twig`, `.html`, or `.css` files), check for brainstorm outputs that define the approved visual design:

1. Check `plans/<feature-slug>/brainstorm.md` for visual design decisions
2. Check `.superpowers/brainstorm/` for HTML mockups (these contain styling decisions as inline styles)
3. If found, extract a **Visual Reference Summary**:
   - Key styling decisions (which component variants, which tokens, which layout patterns)
   - Visual hierarchy: what should be prominent, what should be subdued
   - Specific visual treatments called out in the approved design (e.g., "outline variant for destructive actions", "natural-width buttons")
4. Do NOT embed full HTML mockups in prompts -- extract the decisions, not the markup. Full mockups waste token budget and obscure the intent.
5. Include the file PATH to the mockup so the subagent can reference it if needed

This summary feeds into each UI chunk's prompt as a `## Visual References` section and shapes the visual acceptance criteria in `### Visual Acceptance Criteria`.

### Phase 3: Overlap Analysis

Analyze file paths across all chunks to determine execution strategy:

1. Build a file-to-chunk map: for each file path, list which chunks touch it
2. **No overlap** (file touched by exactly 1 chunk): These chunks CAN run in parallel
3. **Overlap** (file touched by 2+ chunks): These chunks MUST run sequentially
4. Group non-overlapping chunks into parallel groups
5. Order sequential chunks by dependency (earlier chunks first)

Read `references/dependency-ordering.md` for the full ordering algorithm.

**Example:**
```
Chunk A touches: handlers/user.go, models/user.go
Chunk B touches: handlers/product.go, models/product.go
Chunk C touches: handlers/user.go, templates/user.templ

Result:
- A and B: no overlap -> parallel group
- A and C: overlap on handlers/user.go -> sequential (A before C)
- B and C: no overlap -> C can run after A, parallel with B
```

### Phase 3b: Cross-Chunk Namespace Analysis

For projects using client-side state (Datastar signals, React state, Vue refs, etc.), analyze state namespaces across ALL chunks:

1. List every signal/state variable each chunk introduces or modifies
2. Check for name collisions across chunks AND existing app code
3. Check for shell-level vs page-level scope conflicts (e.g., both a global search modal and a page filter using `searchQuery`)

```
Signal namespace map:
  chunk-01: introduces filterStatus, filterYear (page-level, /proposals)
  chunk-02: introduces searchQuery (shell-level, global search modal)
  chunk-03: introduces searchQuery (page-level, /members filter)
  COLLISION: searchQuery used in both chunk-02 (shell) and chunk-03 (page)
  FIX: Rename chunk-03's signal to memberSearchQuery
```

Flag collisions before generating prompts. Do not proceed with namespace conflicts.

### Phase 3c: Usage Count Reconciliation

If the research phase identified a specific count of usages (e.g., "35 instances of popup-dialog"), verify the prompts account for ALL of them:

1. Sum the instances addressed across all chunk prompts
2. Compare to the total from research
3. If the counts don't match, the gap represents unplanned work that will break

```
Usage reconciliation:
  Research found: 35 popup-dialog usages
  Chunk 01 addresses: 12 (governance pages)
  Chunk 02 addresses: 14 (member pages)
  Chunk 03 addresses: 0 (documentation -- miscategorized as text-only)
  TOTAL PLANNED: 26
  GAP: 9 usages unaccounted for
  FIX: Add documentation page conversions to chunk 03
```

This is a mandatory gate. Do not proceed if planned conversions != total usages.

### Phase 3d: Survivor Audit

After deciding what to add, modify, or delete, review what STAYS:

1. For every file that survives unchanged, ask: "Does this file still make sense given what was removed/added?"
2. For shared utilities/base classes, check if they still have enough consumers to justify their existence
3. If a file exists only to serve one remaining consumer, evaluate inlining

```
Survivor audit:
  base.js (108 lines) -- kept for markdown-editor.js (1 consumer, uses 3 of 10 features)
  VERDICT: Inline the 3 used features into markdown-editor.js, delete base.js
```

### Phase 4: Prompt Generation

For each chunk, generate a self-contained execution prompt using the template from `references/prompt-template.md`. Each prompt must be:

1. **Self-contained** -- All context inlined, no external references needed
2. **Specific** -- Exact file paths, exact patterns to follow, exact acceptance criteria
3. **Scoped** -- Only touches the files listed, nothing else
4. **Testable** -- Clear acceptance criteria the subagent can verify
5. **Visually specified** (UI chunks) -- Include the Visual Reference Summary from Phase 2.5 and generate both structural AND visual acceptance criteria (see prompt template)

Write each prompt to `plans/<feature-slug>/prompts/<chunk-id>.md`.

### Phase 5: Manifest Generation

Generate `plans/<feature-slug>/manifest.json` following the schema in `references/manifest-schema.md`.

The manifest encodes:
- Chunk ordering and dependencies
- Parallel groups
- Overlap analysis results
- Feature branch naming
- Execution metadata

### Phase 6: Requirements Coverage Check

Re-read `plans/<feature-slug>/original-prompt.md` and verify every Key Requirement is covered by at least one chunk's acceptance criteria. Produce a coverage map:

```
Requirements Coverage:
  1. [Requirement text] -> chunk-02a (acceptance criterion #3)
  2. [Requirement text] -> chunk-03 (acceptance criterion #1)
  3. [Requirement text] -> NOT COVERED -- adding to chunk-04
```

If any requirement is uncovered, either add it to an existing chunk's acceptance criteria or create a new chunk. Do not proceed with gaps.

### Phase 6b: Prompt Quality Parity Check

Compare prompt detail levels across same-classification chunks to catch context fatigue -- later prompts tend to be less detailed than earlier ones.

1. **Group prompts by classification** (UI, Logic, Trivial, Integration).
2. **For each group, measure:**
   - Line count per prompt
   - Number of acceptance criteria per prompt
   - Number of visual acceptance criteria per prompt (UI/Integration only)
3. **Flag outliers:**
   - If any prompt has fewer than 50% of the group's average line count, flag: "WARNING: [chunk-id] may be under-specified ([N] lines vs group average [M])"
   - If a UI chunk has 0 visual acceptance criteria when siblings have 2+, flag: "WARNING: [chunk-id] has no visual acceptance criteria -- visual requirements may have been dropped during decomposition"
   - If the last prompt in a group is the shortest, this is likely context fatigue -- flag it specifically
4. **Output a parity summary:**
   ```text
   Prompt Quality Parity:
     UI chunks: chunk-01 (82 lines, 4 visual criteria), chunk-03 (45 lines, 1 visual criterion) -- WARNING: chunk-03 under-specified
     Logic chunks: chunk-02 (60 lines), chunk-04 (55 lines) -- OK
   ```
5. **Fix warnings** by expanding under-specified prompts before proceeding to handoff. Add missing context, acceptance criteria, and visual specifications from the plan and research briefs.

### Phase 7: Handoff

If running as part of `/pipeline`, pass the manifest to the adversarial review phase. If running standalone via `/pipeline-prompts`, present the manifest summary and prompt list to the user.

Present a summary:

```
Generated N prompts for feature "<name>":
  Sequential: [chunks that must run in order]
  Parallel groups: [groups of chunks that can run simultaneously]
  Estimated overlap risk: low/medium/high
  Requirements covered: N/N from original prompt

Manifest: plans/<feature-slug>/manifest.json
Prompts: plans/<feature-slug>/prompts/
Original: plans/<feature-slug>/original-prompt.md
```
