# Manifest Schema

The manifest file (`manifest.json`) encodes everything the execution-orchestrator needs to run the prompts autonomously.

## Schema

```json
{
  "feature": "feature-slug",
  "description": "One-line feature description",
  "workflowClass": "feature",
  "decisionProfile": {
    "uncertainty": "low",
    "consequence": "low",
    "rationale": "Approved requirements are bounded and reversibly implemented."
  },
  "executionMode": "full_cli",
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
      "executor": "openrouter"
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
      "executor": "codex"
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
      "executor": "codex"
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

`workflowClass` and `decisionProfile` are separate policy inputs, not cached
execution structure. New manifests copy both unchanged from the user-approved
plan island; absent, duplicated, malformed, or conflicting plan data returns to
the planning user gate and blocks generation. `decisionProfile` is the exact
closed object `{uncertainty: low|medium|high, consequence: low|medium|high,
rationale: non-empty string}`. It never derives or changes `workflowClass`,
`risk`, `overlapRisk`, `estimatedComplexity`, `kind`, `executor`, or
`routingOverride`. Do not copy workflow stages or safety-anchor constants into
this schema; the workflow-kernel's separately versioned trusted policy remains
authoritative.

## Performance Contract

The manifest describes product work, not pipeline closeout. Do not emit an
orchestrator-owned closeout chunk for verification summaries, requirements
cross-checks, post-mortems, cleanup, delivery receipts, PR publication, or issue
disposition. The orchestrator's final stages own those actions. A chunk may
include one only when it also delivers actual product integration code required
by an acceptance criterion.

The default single-run budget is 8 total chunks and 6 `large` chunks. Exceeding
either limit returns to the planning user gate for a campaign split unless the
approved plan contains an explicit single-run rationale. Approval freezes run
scope: newly discovered desirable work goes to a follow-up manifest unless it
blocks correctness of an approved requirement.

## Field Definitions

### Top-level

| Field | Type | Description |
|-------|------|-------------|
| `feature` | string | URL-safe slug for the feature |
| `description` | string | One-line human-readable description |
| `workflowClass` | enum | `chore`, `bug`, `feature`, `hotfix`, `security`, `investigation`, or `migration`. Promptcraft MUST copy the single approved value from the plan into every new manifest; missing/ambiguous plan data blocks and returns to the user gate. A legacy manifest with no field translates as `feature` and records `workflow_class_defaulted=true`; consumers MUST NOT infer a class from prompt text, paths, or chunk kinds. Pass the validated value unchanged into RunSpec, events, receipts, and metrics. Existing security routing and approval overrides remain authoritative. |
| `decisionProfile` | closed object | Required on every new plan and manifest. Exact keys only: `uncertainty`, `consequence`, and `rationale`; both levels use `low|medium|high` and rationale is a non-empty string. Copy the one approved object byte-for-value unchanged. Multiple candidates, extra keys, malformed levels, empty rationale, or a plan/manifest conflict block generation/dispatch. A legacy manifest with no field follows the current standard path and records `decision_profile_defaulted=true`; absence is unknown provenance and MUST NOT be called low/low evidence. |
| `executionMode` | enum | Optional. Closed set: `full_cli`, `codex_native`, `manual_walkthrough`, `generic`, or `generic_host`. This is the single execution-mode vocabulary shared by the execution-orchestrator's progress ledger, chunk receipts, receipt.md, and the workflow-kernel adapters -- `full_cli` (Claude orchestration tools available), `codex_native` (Codex adapter dispatch), `manual_walkthrough` (user is driving some steps), `generic` (neutral host default), `generic_host` (explicitly host-normalized observation). A manifest with no field translates as `generic`. Consumers MUST reject any other value; browser availability is a verification-evidence status, never an execution mode, and worktree isolation is carried by the separate `isolationStrategy` field, never by this one. |
| `baseBranch` | string | Branch to create feature branch from (usually "main") |
| `featureBranch` | string | Name for the feature branch |
| `generatedAt` | string | ISO 8601 timestamp of manifest generation |
| `overlapRisk` | enum | "low" (0-1 overlapping files), "medium" (2-4), "high" (5+) |
| `noMergeOnCompletion` | boolean | Optional. Default `false`. When `true`, the execution-orchestrator runs every chunk and the final review, but does NOT merge the feature branch into `baseBranch`. The caller retains the branch for manual review. Use when you want pipeline automation without the final merge (e.g. review-first workflows, fix-pass runs that should keep the branch open for iteration). |
| `campaignSlug` | string or null | Optional. Campaign identifier for cross-session state tracking. When present, the orchestrator writes `.campaign/state.json` after the run. When null or absent, campaign state is skipped. |

## Decision Leverage Boundary

The `decisionLeverage` section in `routing-policy.json` controls workflow depth
only. Low/low uses the optimized standard path without inferring a cheaper
execution rail. High uncertainty adds exactly one independent planning opinion
and one bounded synthesis. High consequence strengthens the existing
independent verification seam. High/high applies both. Medium combinations use
the current standard depth unless one dimension is high.

Decision leverage never selects a provider or model, changes an executor,
creates a routing override, relaxes a security rule, changes `workflowClass`,
reduces browser/persona coverage, skips review, changes cleanup, or changes run
economics. It does not authorize open debate or a full review for every chunk.
All existing sensitive-path, browser recovery, final review, zero-deferral,
run-size, and exact-owned Docker cleanup rules remain authoritative.

Bootstrap limitation: a run whose already-approved/current manifest predates
this field may derive a profile from its approved plan for explanatory receipts,
but MUST NOT retrofit `decisionProfile` into that current manifest. It stays on
the legacy standard path with `decision_profile_defaulted=true`. Only a newly
generated manifest may carry the approved object.

### Runtime receipt context (not manifest fields)

`isolationStrategy` is detected by the execution orchestrator after manifest
validation, so it is never accepted as planning authority in the top-level
manifest. It is a closed receipt/ledger field separate from `executionMode`:
`per-chunk-worktree` (default) or `sequential-on-branch` (Step 1c detected a
container-mounted test harness rooted at the main checkout). Record it in the
progress ledger, every receipt, `receipt.md`, and the Summary Report. The
workflow-kernel normalizes it to `isolation_strategy`, rejects unknown values
or run-wide discontinuity, and includes it in shadow parity and metrics.

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
| `executor` | enum | Coding execution tool: `"codex"` or `"openrouter"`; legacy `"claude"` remains parseable but normalizes to Codex. Derived from `kind`, `estimatedComplexity`, and the shared `plugins/pipeline/references/routing-policy.json`. See Executor Mapping below. |
| `routingOverride` | object, conditional | Required only when `executor` differs from the routing-policy default. Contains `reasonCode`, concrete `reason`, `splitAttempted`, and `splitBlockedBy`. A config/docs chunk routed to Codex without this object is invalid. |

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

The `executor` field is derived from `kind`, `estimatedComplexity`, and `routing-policy.json`:

| Kind | Executor | Rationale |
|------|----------|-----------|
| `config` / docs | `openrouter` | Documentation and configuration edits are text-heavy and fit cheap large-context models |
| mechanical `logic` | `openrouter` or `codex` | Rename follow-through, test tables, seed data, and migration edits can run on OpenRouter when bounded; Codex is secondary |
| complex `logic` | `codex` | New service methods and refactors need agentic code execution before falling back |
| `ui` | `codex` | UI implementation uses Codex; browser and Live Wires evidence remain mandatory |
| `integration` | `codex` | Cross-chunk wiring and route verification are code-heavy orchestration |

Before overriding a policy-selected OpenRouter chunk because it needs a connector or other host-only tool, split the live-tool operation from offline analysis/config/docs whenever ownership permits. A valid override has this shape:

```json
{
  "routingOverride": {
    "reasonCode": "required-live-tool",
    "reason": "The authenticated connector result determines the same atomic edit.",
    "splitAttempted": true,
    "splitBlockedBy": "The offline edit cannot be specified until the connector returns."
  }
}
```

Allowed `reasonCode` values are `sensitive-path`, `required-live-tool`, `provider-unavailable`, and `quality-floor`. `splitAttempted` must be true for `required-live-tool`; `splitBlockedBy` must explain why a separate offline OpenRouter chunk was not possible. Tool or sensitive-path words appearing in prompt prose are not sufficient evidence for an override.

## Graceful Fallback

If an executor is unavailable, the orchestrator falls back through the Codex/OpenRouter cascade in `model-cascade.json` and records the fallback in the chunk receipt. Claude is non-coding-only. The `executor` field is not advisory: the orchestrator MUST dispatch to the selected coding provider and MUST NOT silently implement a non-native chunk in-process. The only policy-level adjustment is `targets.enforcement.strategy` for a named flexible bucket; it does not mutate the manifest and must be recorded as a target-pressure adjustment in the chunk receipt.

## Naming Conventions

- Feature slug: lowercase, hyphens, no spaces (`add-proposal-voting`)
- Chunk IDs: `NN-description` for sequential, `NNx-description` for parallel (where x is a/b/c)
- Parallel groups: uppercase letters (A, B, C)
- Feature branch: `feature/<feature-slug>`
- Chunk branches: `pipeline/<feature-slug>/<chunk-id>`
