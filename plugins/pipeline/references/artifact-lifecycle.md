# Artifact Lifecycle Policy

Governs all files that pipeline and dm-review plugins create in downstream repos.

## Tiers

| Tier | Lifecycle | Gitignored | Cleanup |
|------|-----------|------------|---------|
| **1 — Ephemeral** | Auto-deleted on run completion (success or failure) | Yes | Orchestrator Step 5b |
| **2 — Run-scoped** | Deleted after successful run; preserved on failure for debugging | Yes | Orchestrator Step 5b |
| **3 — Feature-scoped** | Persist until user disposes via delivery gate | No | User choice at Phase 7 GATE |
| **4 — Durable** | Permanent (ai-memory, committed code, Notion) | N/A | Never |

## Artifact Inventory

### Pipeline artifacts (`plans/<feature-slug>/`)

| File | Tier | Notes |
|------|------|-------|
| `baselines/*.png` | 1 | Pre-implementation screenshots from assess phase |
| `baselines-pre-fix/*.png` | 1 | Fix-pass before screenshots |
| `baselines-post-fix/*.png` | 1 | Fix-pass after screenshots |
| `screenshots/*.png` | 1 | Phase 7 verification screenshots |
| `prompts/*.md` | 2 | Chunk execution prompts consumed by orchestrator |
| `manifest.json` | 2 | Chunk ordering and dependency metadata |
| `brainstorm.md` | 2 | Design decisions (key choices captured in plan.md) |
| `original-prompt.md` | 3 | User's verbatim input — ground truth |
| `assessment.md` | 3 | Current state report with cached Key Requirements |
| `research.md` | 3 | Findings from research phase |
| `plan.md` | 3 | Implementation plan |
| `final-requirements-crosscheck.md` | 3 | Delivery proof with evidence types |
| `receipt.md` | 3 | Compact post-cleanup summary (written by Step 5b) |

### Pipeline worktrees

| Path | Tier | Notes |
|------|------|-------|
| `.worktrees/pipeline/<feature>/<chunk>/` | 1 | Per-chunk isolated workspace, auto-removed in Step 3j |

### dm-review artifacts

| Path | Tier | Notes |
|------|------|-------|
| `.claude/ux-review/screenshots/<date>/*.png` | 1 | Rotated: only today's date kept |
| `.claude/ux-review/manifest.json` | 2 | Overwritten each run |
| `todos/*-pending-*.md` | 3 | Active findings — persist until resolved |
| `todos/*-done-*.md` | 1 | Resolved findings — auto-cleaned before next review |
| `todos/*-deferred-*.md` | 3 | Tracked debt with justifications — never auto-cleaned |

### Durable records (Tier 4)

| Record | Store | Written by |
|--------|-------|------------|
| Pipeline session observation | ai-memory (`DepotPlugin:pipeline`) | Orchestrator Step 5 |
| Review session observation | ai-memory (project entity) | review-memory-recorder agent |
| Activity log row | Notion ops dashboard | Pipeline Phase 7 / dm-review Phase 7c |

## Cleanup Rules

### On successful pipeline completion (Step 5b)

1. Write `plans/<feature-slug>/receipt.md`
2. Delete all Tier 1 files: `rm -rf plans/<slug>/baselines/ baselines-pre-fix/ baselines-post-fix/ screenshots/`
3. Delete all Tier 2 files: `rm -rf plans/<slug>/prompts/` and `rm -f plans/<slug>/manifest.json plans/<slug>/brainstorm.md`
4. Report: `Artifact cleanup: removed N files, retained M feature-scoped files`

### On failed pipeline run (Step 5b)

1. Write `plans/<feature-slug>/receipt.md` with failure details
2. Delete Tier 1 only (screenshots valueless after failure)
3. Preserve Tier 2 (prompts/manifest useful for retry/debugging)
4. Report: `Artifact cleanup (partial — run failed): removed N ephemeral files, preserved prompts for debugging`

### On user "Done" at Phase 7 GATE

1. Run standard cleanup (Tier 1 + 2)
2. Also delete Tier 3 files, leaving only `receipt.md`

### dm-review screenshot rotation

Before creating today's screenshot directory, delete all previous date directories. Only the current day's screenshots survive to the next review.

### dm-review todo lifecycle

- `*-done-*.md` files auto-cleaned before creating new todos (Phase 6 pre-cleanup)
- `*-deferred-*.md` files never auto-cleaned — represent tracked debt
- `*-pending-*.md` files persist until resolved via `/dm-review-fix`

## Receipt Format

Written by Step 5b after cleanup. Under 2 KB. This is the durable record that remains after ephemeral/run-scoped artifacts are deleted.

```markdown
# Pipeline Receipt: <feature-slug>

- Date: YYYY-MM-DD
- Branch: <featureBranch>
- Merge: CLEAN | APPROVE WITH FIXES | BLOCKS MERGE
- Chunks: N executed, M parallel
- Mode: full_cli | curl_fallback

## Evidence
| # | Requirement | Evidence |
|---|-------------|----------|
| 1 | <text> | grep:`...` |
| 2 | <text> | screenshot (cleaned) |

## Cleanup
- Ephemeral removed: N files
- Run-scoped removed: N files
- Feature-scoped retained: N files
- Deferred findings: none | <list>
```

## Gitignore Enforcement

See `gitignore-template.md` for canonical entries. The execution-orchestrator's Step 0d enforces these entries at the start of every run — no passive suggestions.
