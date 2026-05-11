# Manifest Schema

The manifest file (`manifest.json`) encodes everything the execution-orchestrator needs to run the prompts autonomously.

## Schema

```json
{
  "feature": "feature-slug",
  "description": "One-line feature description",
  "baseBranch": "main",
  "featureBranch": "feature/feature-slug",
  "generatedAt": "2026-03-27T10:00:00Z",
  "overlapRisk": "low|medium|high",
  "noMergeOnCompletion": false,
  "campaignSlug": null,
  "chunks": [
    {
      "id": "01-database-migration",
      "title": "Add vote columns to proposals table",
      "prompt": "prompts/01-database-migration.md",
      "level": 0,
      "parallelGroup": null,
      "dependsOn": [],
      "filesToModify": [
        "internal/database/migrations/003_add_votes.sql"
      ],
      "companionSkills": ["assembly:development"],
      "estimatedComplexity": "small",
      "kind": "logic",
      "executor": "codex"
    },
    {
      "id": "02a-vote-handler",
      "title": "Add vote handler and routes",
      "prompt": "prompts/02a-vote-handler.md",
      "level": 1,
      "parallelGroup": "A",
      "dependsOn": ["01-database-migration"],
      "filesToModify": [
        "internal/handler/vote.go",
        "internal/router/routes.go"
      ],
      "companionSkills": ["assembly:development"],
      "estimatedComplexity": "medium",
      "kind": "logic",
      "executor": "codex"
    },
    {
      "id": "02b-vote-display",
      "title": "Add vote count display to proposal template",
      "prompt": "prompts/02b-vote-display.md",
      "level": 1,
      "parallelGroup": "A",
      "dependsOn": ["01-database-migration"],
      "filesToModify": [
        "internal/view/proposal/show.templ",
        "internal/view/proposal/components.templ"
      ],
      "companionSkills": ["assembly:development", "live-wires:livewires"],
      "estimatedComplexity": "medium",
      "kind": "ui",
      "executor": "claude"
    },
    {
      "id": "03-integration",
      "title": "Wire voting into proposal detail page with Datastar",
      "prompt": "prompts/03-integration.md",
      "level": 2,
      "parallelGroup": null,
      "dependsOn": ["02a-vote-handler", "02b-vote-display"],
      "filesToModify": [
        "internal/handler/proposal.go",
        "internal/view/proposal/show.templ"
      ],
      "companionSkills": ["assembly:development"],
      "estimatedComplexity": "medium",
      "kind": "integration",
      "executor": "claude"
    }
  ],
  "executionPlan": {
    "levels": [
      {
        "level": 0,
        "strategy": "sequential",
        "chunks": ["01-database-migration"]
      },
      {
        "level": 1,
        "strategy": "parallel",
        "groups": {
          "A": ["02a-vote-handler", "02b-vote-display"]
        }
      },
      {
        "level": 2,
        "strategy": "sequential",
        "chunks": ["03-integration"]
      }
    ],
    "totalChunks": 4,
    "parallelChunks": 2,
    "sequentialChunks": 2,
    "maxConcurrency": 2
  }
}
```

## Source of Truth

The `chunks` array is authoritative. The `executionPlan` object is a cached denormalization: it groups chunks by level for convenient consumption by the execution-orchestrator. If they ever disagree (e.g. a chunk's `level` or `parallelGroup` was edited), the `chunks` data wins. The execution-orchestrator validates consistency at startup by recomputing the level groups from `chunks` and comparing to `executionPlan`.

## Field Definitions

### Top-level

| Field | Type | Description |
|-------|------|-------------|
| `feature` | string | URL-safe slug for the feature |
| `description` | string | One-line human-readable description |
| `baseBranch` | string | Branch to create feature branch from (usually "main") |
| `featureBranch` | string | Name for the feature branch |
| `generatedAt` | string | ISO 8601 timestamp of manifest generation |
| `overlapRisk` | enum | "low" (0-1 overlapping files), "medium" (2-4), "high" (5+) |
| `noMergeOnCompletion` | boolean | Optional. Default `false`. When `true`, the execution-orchestrator runs every chunk and the final review, but does NOT merge the feature branch into `baseBranch`. The caller retains the branch for manual review. Use when you want pipeline automation without the final merge (e.g. review-first workflows, fix-pass runs that should keep the branch open for iteration). |
| `campaignSlug` | string or null | Optional. Campaign identifier for cross-session state tracking. When present, the orchestrator writes `.campaign/state.json` after the run. When null or absent, campaign state is skipped. |

### Chunk

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique chunk identifier, used in branch names and worktree paths |
| `title` | string | Human-readable chunk title |
| `prompt` | string | Relative path to the prompt file |
| `level` | number | Execution level (0 = first) |
| `parallelGroup` | string or null | Group ID for parallel chunks, null if sequential |
| `dependsOn` | string[] | Chunk IDs that must complete before this one starts |
| `filesToModify` | string[] | Files this chunk will create or modify |
| `companionSkills` | string[] | Skills to load in format "plugin:skill" |
| `estimatedComplexity` | enum | "small" (1-2 files), "medium" (3-5 files), "large" (6+ files) |
| `kind` | enum | Chunk type classification: `"ui"`, `"logic"`, `"integration"`, or `"config"`. Inferred from `filesToModify` during prompt generation. Used by the execution-orchestrator for evaluation depth and by the `executor` field for tool routing. See Classification Rules below. |
| `executor` | enum | Execution tool: `"codex"` or `"claude"`. Derived from `kind`. Determines whether the chunk is dispatched to Codex (OpenAI) or Claude for implementation. See Executor Mapping below. |

### Execution Plan

| Field | Type | Description |
|-------|------|-------------|
| `levels` | array | Ordered list of execution levels |
| `levels[].level` | number | Level number |
| `levels[].strategy` | enum | "sequential" or "parallel" |
| `levels[].chunks` | string[] | Chunk IDs for sequential levels |
| `levels[].groups` | object | Group ID -> chunk ID array for parallel levels |
| `totalChunks` | number | Total number of chunks |
| `parallelChunks` | number | Number of chunks that will run in parallel |
| `sequentialChunks` | number | Number of chunks that must run sequentially |
| `maxConcurrency` | number | Maximum simultaneous worktrees needed |

## Classification Rules

The `kind` field is inferred from `filesToModify` during prompt generation (Phase 1 of promptcraft):

| Kind | Condition |
|------|-----------|
| `ui` | Any file ends in `.templ`, `.twig`, `.html`, `.css`, or lives in a `pages/`, `templates/`, `views/` directory |
| `logic` | Files end in `.go`, `.py`, `.ts`, `.php` and are handlers, services, or migrations -- no templates |
| `integration` | Prompt contains wiring verbs ("wire," "integrate," "connect") OR chunk modifies route files, `main.go`, or navigation templates |
| `config` | Only `.md`, `.json`, `.yaml`, `.toml`, documentation, or configuration files |

When a chunk's files span multiple categories, classify up: `ui` > `integration` > `logic` > `config`.

## Executor Mapping

The `executor` field is derived from `kind`:

| Kind | Executor | Rationale |
|------|----------|-----------|
| `logic` | `codex` | Backend-only work doesn't need Claude's visual reasoning |
| `config` | `codex` | Documentation and configuration edits are mechanical |
| `ui` | `claude` | Visual verification and Live Wires judgment require Claude |
| `integration` | `claude` | Cross-chunk wiring and route verification require Claude's broader context |

## Graceful Fallback

If Codex auth is absent or the Codex plugin is not installed, all chunks execute on Claude regardless of the `executor` field. The orchestrator logs: `"Codex unavailable for chunk [id], falling back to Claude execution."` and proceeds with the existing Claude subagent dispatch path. The `executor` field is advisory -- it never blocks execution.

## Naming Conventions

- Feature slug: lowercase, hyphens, no spaces (`add-proposal-voting`)
- Chunk IDs: `NN-description` for sequential, `NNx-description` for parallel (where x is a/b/c)
- Parallel groups: uppercase letters (A, B, C)
- Feature branch: `feature/<feature-slug>`
- Chunk branches: `pipeline/<feature-slug>/<chunk-id>`
