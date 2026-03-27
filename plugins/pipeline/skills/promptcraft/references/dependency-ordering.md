# Dependency Ordering Algorithm

Determines which chunks can run in parallel and which must run sequentially based on file overlap and logical dependencies.

## Step 1: Build File-to-Chunk Map

For each chunk, list every file it will read-to-modify or create:

```
chunk-01: [file_a, file_b]
chunk-02: [file_c, file_d]
chunk-03: [file_a, file_e]
chunk-04: [file_f]
```

Note: "Files to Read (for context)" do NOT count as overlap. Only files being modified or created matter.

## Step 2: Detect Overlaps

For each pair of chunks, check if their modify/create file lists intersect:

```
chunk-01 vs chunk-02: no overlap
chunk-01 vs chunk-03: overlap on file_a -> SEQUENTIAL
chunk-01 vs chunk-04: no overlap
chunk-02 vs chunk-03: no overlap
chunk-02 vs chunk-04: no overlap
chunk-03 vs chunk-04: no overlap
```

## Step 3: Apply Logical Dependencies

Some dependencies are logical, not file-based:

1. **Schema before code** -- Database migrations must complete before code that uses new tables/columns
2. **Types before implementation** -- If a chunk defines types/interfaces that another chunk implements, types first
3. **Core before integration** -- Individual components before the code that wires them together
4. **Backend before frontend** -- If frontend calls new API endpoints, backend first (unless mocking)

Add these as explicit dependencies even if there's no file overlap.

## Step 4: Build Dependency Graph

Create a directed acyclic graph (DAG):

```
chunk-01 -> chunk-03 (file overlap)
chunk-01 -> chunk-04 (logical: schema before code)
```

Chunks with no incoming edges and no overlaps with each other can form parallel groups.

## Step 5: Assign Execution Order

1. **Level 0:** Chunks with no dependencies (can all run in parallel if no mutual overlap)
2. **Level 1:** Chunks that depend only on Level 0 chunks
3. **Level N:** Chunks that depend on Level N-1 chunks

Within each level, group non-overlapping chunks into parallel groups.

## Step 6: Encode in Manifest

Each chunk gets:
- `dependsOn`: list of chunk IDs that must complete first
- `parallelGroup`: group identifier (chunks in same group run simultaneously), or null if sequential
- `level`: execution level (0 = first, higher = later)

## Example

Plan: "Add proposal voting to Assembly"

```
chunk-01: Add vote columns to proposals table (migration)
  Files: internal/database/migrations/003_add_votes.sql
  Dependencies: none
  Level: 0

chunk-02a: Add vote handler and routes
  Files: internal/handler/vote.go, internal/router/routes.go
  Dependencies: chunk-01 (needs new columns)
  Level: 1

chunk-02b: Add vote count display to proposal template
  Files: internal/view/proposal/show.templ, internal/view/proposal/components.templ
  Dependencies: chunk-01 (needs new columns for display)
  Level: 1

chunk-03: Wire voting into proposal detail page with Datastar
  Files: internal/handler/proposal.go, internal/view/proposal/show.templ
  Dependencies: chunk-02a (needs vote handler), chunk-02b (needs updated template)
  Level: 2
  Note: Overlaps with chunk-02b on show.templ, so chunk-02b must complete first
```

Result:
- Level 0: [chunk-01] (sequential, alone)
- Level 1: [chunk-02a, chunk-02b] (parallel group A -- no file overlap)
- Level 2: [chunk-03] (sequential, after both Level 1 chunks)

## Edge Cases

**Circular overlap:** If chunk A and chunk B both modify file X, they cannot be parallel. Pick an order based on logical flow (which change makes sense first?).

**Large overlap:** If most chunks touch the same files, parallelism is minimal. This is a signal that the plan may need to be restructured into larger, more independent chunks.

**Single-file chunks:** A chunk that only modifies one file is easy to parallelize. Prefer smaller, focused chunks over large multi-file chunks.

**Shared config files:** Files like `routes.go` or `main.go` that many chunks touch should be handled in a final integration chunk, not in each individual chunk. Extract the "add route" step into the integration chunk.
