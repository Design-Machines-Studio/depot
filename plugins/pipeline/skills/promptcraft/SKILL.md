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

### Phase 4: Prompt Generation

For each chunk, generate a self-contained execution prompt using the template from `references/prompt-template.md`. Each prompt must be:

1. **Self-contained** -- All context inlined, no external references needed
2. **Specific** -- Exact file paths, exact patterns to follow, exact acceptance criteria
3. **Scoped** -- Only touches the files listed, nothing else
4. **Testable** -- Clear acceptance criteria the subagent can verify

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
