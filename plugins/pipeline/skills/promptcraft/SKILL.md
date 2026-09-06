---
name: promptcraft
description: Self-contained execution prompts and a manifest from a plan, with overlap-aware dependency ordering for parallel vs sequential worktree execution. Use when breaking a plan into executable chunks for autonomous worktree-based execution. Invoke with /pipeline-prompts or as part of /pipeline.
---

# Execution Prompt Generator

Transform a plan into self-contained execution prompts with overlap-aware dependency ordering. Produces a manifest that the execution-orchestrator consumes directly.

## Input

1. **Plan file** -- a pipeline `plan.html` carrying a `#pipeline-data` JSON island (`chunks`, `decisions`, `requirementsCoverage`). When invoked standalone on a hand-written markdown plan, parse the prose directly; within `/pipeline` the plan is HTML.
2. **Original prompt** -- the user's verbatim input at `plans/<feature-slug>/original-prompt.md` (stays markdown; requested mechanisms are not automatically approved scope)
3. **Research Brief** (optional) -- `research.html` from the research skill
4. **Assessment Brief** (required within `/pipeline`) -- `assessment.html` from the assess skill. Its `keyRequirements` island is authoritative only after the combined discovery response; its rendered Project Alignment section is the compact source for goal, non-goals, constraints, and ownership.

## Process

### Phase 0: Artifact Format Policy

Pipeline planning artifacts (`assessment`, `research`, `brainstorm`, `plan`) are **HTML carrying a JSON data island**, not markdown. Read their structured data with the island extractor rather than grepping rendered prose:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/extract-json-island.sh" plans/<feature-slug>/plan.html
```

The plan island's `chunks` array seeds Phase 1; each chunk's `n` + `slug` map 1:1 onto the `prompts/NN-<slug>.md` written in Phase 4. The assessment island's `keyRequirements` is the cached requirements source for the Phase 6 coverage check. Generated prompts and `manifest.json` stay **markdown/JSON** -- agent-only handoffs, not human-facing artifacts. See `references/templates/README.md`.

### Phase 1: Plan Decomposition

A chunk is a logically complete unit (one feature aspect, one migration, one component), implementable without seeing intermediate results of other chunks, and testable in isolation (own acceptance criteria).

**Decomposition rules:**
0. Before chunking, require the plan prose to state the current project goal, why the work is appropriate now, explicit non-goals, and the **Smallest Usable Implementation**. Every chunk must map through the existing requirements-coverage map to at least one approved requirement or project outcome. For every proposed new abstraction, service, policy layer, background process, cache, transaction ledger, approval ceremony, receipt family, compatibility layer, or generalized extension point, the plan must name its current consumer, a concrete present failure or realistic reachable harm, and what it replaces or why direct code is inadequate; delete unsupported machinery or retain it only as a non-blocking future idea.
1. Database/schema changes are always their own chunk and always run first
2. Backend and frontend work on different files can be separate parallel chunks
3. Integration work (wiring things together) depends on the pieces it connects
4. Test-only chunks are rare -- tests should live with their implementation chunk
5. Configuration/deployment chunks run last
6. Do not create an orchestrator-owned closeout chunk. Verification summaries, requirements cross-checks, post-mortems, cleanup, delivery receipts, PR publication, and issue disposition belong to the pipeline's final stages; they may appear in a product chunk only when that chunk also contains real integration code required by its acceptance criteria.
7. After determining `filesToModify` for each chunk, classify its `kind` using the file-extension heuristic:
   - `ui`: any served or product-rendered `.templ`, `.twig`, `.html`, `.css`, or files in `pages/`, `templates/`, `views/`
   - `logic`: `.go`, `.py`, `.ts`, `.php` handlers/services/migrations without templates
   - `integration`: prompt contains wiring verbs ("wire," "integrate," "connect") OR modifies route files / `main.go`
   - `config`: `.md`, `.json`, `.yaml`, `.toml`, docs, and unserved non-rendered planning HTML under `plans/**` (including `plans/**/work-paths.html`)

   Then derive `executorRole`, `executorCapabilities`, and `executorEffort` from
   `plugins/pipeline/references/routing-policy.json`:
   - bounded config, docs, and mechanical work -> `builder-fast`;
   - complex logic, UI, and integration -> `builder-deep`;
   - add `browser`, `tool-use`, `long-context`, or `structured-output` only
     when the chunk actually requires that capability.

   Planning HTML is an explicit narrow exception to the `.html` UI trigger: a chunk containing only planning Markdown/JSON/YAML plus unserved `plans/**.html` artifacts remains `config` and `builder-fast`. If splitting separates offline planning artifacts from served UI or live-tool work, split it; mixed or uncertain product surfaces classify up: `ui` > `integration` > `logic` > `config`.

   Then classify rendered-output applicability independently. Every new chunk
   MUST carry `renderedSurface: required|not_applicable` and a non-empty
   `renderedSurfaceRationale`. Use `required` when the chunk changes a served
   route, rendered page/template/component, browser interaction, visible
   output, or visual/browser acceptance criterion. Use `not_applicable` only
   when every UI/integration syntactic trigger is demonstrably unserved or
   non-rendering, such as a planning `.html` artifact or non-HTTP CLI
   `main.go`; name the triggering files and absence of a product route/output
   in the rationale. Mixed or uncertain chunks are `required`. This field
   controls browser/persona/visual/Datastar evidence only; it never changes
   `kind`, role routing, or review depth.

   Split live-tool work from offline analysis/config/docs whenever ownership and dependency order permit. If a chunk's role, capabilities, or effort differs from the policy default, add a closed `routingOverride` with the replacement role fields, `reasonCode`, and concrete `reason`. The override may not select or encode a provider, model, transport, family, subscription, or billing source.

**Run-size and scope budget:**

- Default to no more than 8 total chunks and no more than 6 chunks classified
  `large`. This is a run budget, not permission to make oversized chunks.
- If the complete proposal exceeds either limit, return to the planning user
  discovery gate with the total scope and the smaller usable alternative before
  generating any sibling campaign. Campaign decomposition is not permission to
  hide an oversized design. A single oversized run requires an explicit
  approved rationale in the plan; promptcraft must not invent one.
- Freeze scope when the execution prompts are approved. New desirable work is
  written to a follow-up manifest unless it is a correctness blocker for an
  approved requirement. Do not expand a running chunk merely because adjacent
  cleanup or polish becomes visible.

**Decision profile and leverage gate:** Read exactly one approved
`decisionProfile` from the plan island and copy it unchanged: a closed object
with exactly `uncertainty`, `consequence` (each `low|medium|high`), and a
non-empty `rationale`. Extra keys, malformed values, multiple profiles, or
conflict with approved upstream data blocks prompt generation and returns to
the combined discovery gate.

Keep `decisionProfile` distinct from `workflowClass`, `risk`, `overlapRisk`,
`estimatedComplexity`, `kind`, `renderedSurface`, `executorRole`,
`executorCapabilities`, `executorEffort`, and
`routingOverride`. Apply the
`decisionLeverage` section from `routing-policy.json` to workflow depth only:
low/low uses the optimized current path; high uncertainty adds one independent
planning opinion plus one bounded synthesis; high consequence strengthens the
existing independent verification seam; high/high applies both; all other
combinations keep standard depth. Never expand this into debate or full review
per chunk. It cannot select roles, capabilities, effort, concrete routing, relax security, alter
workflow class, reduce browser/persona evidence, weaken cleanup, or alter
economics.

Legacy input with no profile is consumption-only compatibility: keep the
current standard path and record `decision_profile_defaulted=true`. This is
unknown provenance, not low/low evidence. Do not generate a new manifest from
legacy absence; during this bootstrap an already-generated current manifest
must not be retrofitted even if its approved plan can explain a profile.

### Phase 2: Context Extraction

For each chunk, extract from the plan, research brief, and assessment brief:
the larger approved project goal it serves; its purpose and the approved
requirement or project outcome it addresses; boundaries (relevant non-goals,
ownership boundary, scope limits); the specific deliverable; every file the
chunk will read or modify; existing patterns to follow; only the relevant
research findings; acceptance criteria; and companion skills.

Do not paste the whole roadmap, assessment, research brief, or Project snapshot
into a prompt; use the existing Context section and requirement identifiers,
not a second project-goal identifier system. Follow
`references/prompt-template.md` only when assembling a chunk prompt, never
during decomposition.

### Phase 2.5: Visual Reference Extraction

For chunks with `renderedSurface: required`, first read any applicable
`prototypeReference` and `prototypeParity` entries from the assessment/plan
island. Load `plugins/pipeline/references/prototype-authority.md` when a declared
counterpart exists. Then check for brainstorm outputs that define additional
approved visual design: read the `visualDecisions` island of
`plans/<feature-slug>/brainstorm.html` with
`references/templates/extract-json-island.sh`, and check
`.superpowers/brainstorm/` for HTML mockups (styling decisions as inline
styles).

Extract a **Visual Reference Summary** plus paths. Do not paste complete
mockups or whole templates, but retain the exact short structural excerpts,
component calls, Live Wires class strings, literal copy, metadata phrasing, and
action order needed to prevent drift. For every chunk with a counterpart,
carry the canonical prototype repository and exact commit, relevant prototype
source files under `Files to Read`, prototype/target route-state-viewports,
intentional differences, and both source and browser acceptance criteria.
This summary feeds each rendered-surface chunk's prompt as a
`## Visual References` section and shapes `### Visual Acceptance Criteria`.

### Phase 3: Overlap Analysis

Analyze file paths across all chunks to determine execution strategy:

1. Build a file-to-chunk map: for each file path, list which chunks touch it
2. **No overlap** (file touched by exactly 1 chunk): these chunks CAN run in parallel
3. **Overlap** (file touched by 2+ chunks): these chunks MUST run sequentially
4. Group non-overlapping chunks into parallel groups; order sequential chunks by dependency (earlier chunks first)

Load `references/dependency-ordering.md` only when two chunks share files or one consumes another's output.

### Phase 3b: Cross-Chunk Namespace Analysis

For projects using client-side state (Datastar signals, React state, Vue refs, etc.), list every signal/state variable each chunk introduces or modifies and check for name collisions across chunks AND existing app code, including shell-level vs page-level scope conflicts (e.g., a global search modal and a page filter both using `searchQuery`). Flag collisions before generating prompts and rename (e.g., to `memberSearchQuery`); do not proceed with namespace conflicts.

### Phase 3c: Usage Count Reconciliation

If the research phase identified a specific count of usages (e.g., "35 instances of popup-dialog"), sum the instances addressed across all chunk prompts and compare to the research total; any gap is unplanned work that will break. This is a mandatory gate: do not proceed if planned conversions != total usages.

### Phase 3d: Survivor Audit

After deciding what to add, modify, or delete, review what STAYS:

1. For every file that survives unchanged, ask: "Does this file still make sense given what was removed/added?"
2. Shared utilities/base classes must still have enough consumers to justify existence; a file serving one remaining consumer is a candidate for inlining
3. **Automatic zero-caller check:** for every helper, constant, or function defined in a file listed in `filesToModify`, grep the codebase for its callers. If the proposed changes leave it with zero callers, flag as "survivor needs inlining or deletion."

### Phase 3e: Stable Anchors Audit

Line numbers are time-bounded: an interstitial chunk may rewrite the file before
Phase 6 executes. When a draft prompt cites line numbers, load
`plugins/pipeline/references/promptcraft-stable-anchors.md` and apply its
anchor ranking and re-verification rule. A prompt set that already anchors on
named symbols, components, heading slugs, or table/column names does not load
it.

### Phase 3f/3g: Migration Numbering and Generated Templ Gates

When the plan touches `.sql` migrations or `.templ` sources, load
`plugins/pipeline/references/promptcraft-migration-templ-gates.md` and apply
both gates. When it touches neither, do not load it.

### Phase 3h: Assembly Mutation Applicability Gate

Applies only when the chunk is an Assembly mutation, or actually alters authentication, middleware, an Authorizer action/resource, a privileged read/write, a role/member/account/install/module permission, a privileged UI capability, or a membership/settings/permissions surface. When it does, load `plugins/pipeline/references/promptcraft-applicability-gates.md` and apply this gate. Path names alone are review hints, not proof.

### Phase 3i: Visual Acceptance Criteria Gate

Applies only to chunks with `renderedSurface: required`; load `plugins/pipeline/references/promptcraft-applicability-gates.md` for the rendered-impression bar and the shared-component Visual Parity Criterion. A chunk marked `not_applicable` must not fabricate rendered impressions.

When a prototype counterpart applies, acceptance criteria also require the
builder to inspect prototype source before editing; search existing target and
Live Wires components before creating one; preserve settled hierarchy,
wrappers, classes, copy, action order, and control placement unless a named
approved requirement requires divergence; compare source after editing; compare
matched renders; and record intentional production differences rather than
silently redesigning. Matching screenshots never waive source comparison, and
matching classes never waive browser comparison.

### Phase 3j: UX Task Selection Gate

When the target repo contains `tests/ux/` and at least one chunk is
`renderedSurface: required`, load
`plugins/pipeline/references/promptcraft-ux-task-selection.md` and apply it.
Otherwise do not load it.

### Phase 3k: Parallel Prompt Isolation Gate

Sibling parallel prompts must not cross-reference each other: "after chunk-02 adds the handler" is broken if chunk-02 runs concurrently. For each parallel group, grep prompt text for sibling chunk IDs; any cross-reference is a BLOCKER -- restructure as sequential dependency or inline the referenced context.

### Phase 3l: Manifest Schema Conformance Gate

Validate the generated manifest before handoff with `plugins/pipeline/references/validate-role-manifest.sh`. Every chunk object in the authoritative `chunks[]` array must include: `id`, `level`, `title`, `prompt`, `kind`, `renderedSurface`, `renderedSurfaceRationale`, `executorRole`, `executorCapabilities`, `executorEffort`, `filesToModify`, `dependsOn`, `companionSkills`, `estimatedComplexity`; missing fields cause orchestrator dispatch failures. `level` is a nonnegative integer. `renderedSurface` accepts only `required|not_applicable`; its rationale must be non-empty, and `not_applicable` must account for every UI/integration syntactic trigger. Omit `routingOverride` when no override occurred.

Every new manifest carries the explicit top-level `workflowClass` copied unchanged from the approved plan island (`chore|bug|feature|hotfix|security|investigation|migration`). If the plan does not contain exactly one approved value, return to the combined discovery gate; promptcraft never infers it from filenames, chunk kinds, prompt prose, risk, or keywords. The legacy absent-field default belongs only to manifest consumption and records `feature` plus `workflow_class_defaulted=true`.

Every new manifest also carries the exact approved top-level
`decisionProfile`. Validate the closed shape and exact plan/manifest equality;
reject malformed, multiple, extra-key, or conflicting profiles. Never infer it
from `workflowClass`, risk, complexity, kind, role, or routing data.

Every new manifest also carries the approved branch and final-review controls.
Validate exact plan/manifest equality for `baseBranch`, `featureBranch`,
`branchMode`, `expectedFeatureHead`, `finalReviewMode`, and
`finalReviewRationale`.
`branchMode: reuse` requires exact remote-head hex and forbids the create-mode
initial push; `create` requires the expected head to be null/absent.
`finalReviewMode: quick` requires explicit approval, non-high consequence, and
a proportionate rationale; security-sensitive final diffs still escalate to
full. These controls never weaken per-chunk review or verification.

### Phase 3l.5: Behavioral Contract Readiness Gate

When the repository carries a workflow-kernel verification profile, load
`plugins/pipeline/references/promptcraft-behavioral-contract.md` and prepare the
deterministic contract inputs it specifies. With no such profile, record that
the contract is not applicable and do not load it.

### Phase 3m: Fixture SDK Conformance Gate

**Trigger:** the chunk touches `internal/fixtures/`, the `Module` interface, or a fixture SDK path. When it does, load `plugins/pipeline/references/promptcraft-applicability-gates.md` for the negative-test acceptance criteria and the same-chunk conformance-harness requirement.

### Phase 3n: Production Readiness Preflight Gate

**Trigger:** the chunk touches config loading, the updater, release tooling, shutdown, or key rotation. When it does, load `plugins/pipeline/references/promptcraft-applicability-gates.md` for the eight preflight acceptance criteria.

### Phase 3o: Datastar-First Gate

**Trigger:** the project is Go + Templ + Datastar and the chunk has `renderedSurface: required`. When it does, load `plugins/pipeline/references/promptcraft-applicability-gates.md` for the attribute-naming, bundle-presence, no-new-JS, and `companionSkills` requirements.

### Phase 4: Prompt Generation

For each chunk, generate a self-contained execution prompt using `references/prompt-template.md`: **self-contained** (all context inlined), **specific** (exact file paths, patterns, acceptance criteria), **scoped** (touches only the listed files), **testable**, **visually specified** when `renderedSurface: required` (Phase 2.5 Visual Reference Summary plus structural AND visual acceptance criteria), and **project-aligned** -- its Context names the larger project goal, why the
chunk exists, the approved requirement or outcome it addresses, and only the
relevant non-goals and ownership boundary.

Write each prompt to `plans/<feature-slug>/prompts/<chunk-id>.md`, where `<chunk-id>` is the `NN-<slug>` from the plan island's `chunks` (zero-padded, ordered; e.g. `00-preflight`, `01-reader-service`, ... `10-doc-sync`). Prompts stay **markdown** -- Tier 2 (run-scoped) agent-only artifacts, auto-deleted by the orchestrator's cleanup phase after successful execution.

### Phase 5: Manifest Generation

Generate `plans/<feature-slug>/manifest.json`. Load `references/manifest-schema.md` only to resolve a field not already specified in this skill. The manifest is a Tier 2 (run-scoped) artifact -- auto-deleted after successful execution.

Copy the Phase 3l controls -- top-level `workflowClass`, the exact closed
`decisionProfile`, `baseBranch`, `featureBranch`, `branchMode`,
`expectedFeatureHead`, `finalReviewMode`, and `finalReviewRationale` --
unchanged from the approved plan data island into every generated manifest.
Missing, ambiguous, malformed, multiple, or conflicting plan data blocks
generation and returns to the user gate.

Each chunk object in the manifest MUST include `kind`, `renderedSurface`, `renderedSurfaceRationale`, `executorRole`, `executorCapabilities`, and `executorEffort` fields (classified independently in Phase 1, step 7). An approved deviation carries the closed `routingOverride` object described in Phase 1. The manifest encodes chunk ordering and dependencies, parallel groups, overlap analysis results, feature branch naming, branch creation or exact-head reuse semantics, execution metadata, and the approved workflow-class, decision-profile, final-review-mode, and rendered-surface controls.

When prototype authority applies, copy the compact optional
`prototypeReference` and only each chunk's relevant `prototypeParity` entries
into the manifest. These are projections of the existing assessment/plan data
island, not a new registry or evidence store.

### Phase 6: Requirements Coverage Check

Read the approved Key Requirements from the `keyRequirements` island of `plans/<feature-slug>/assessment.html` (`extract-json-island.sh`), re-reading `plans/<feature-slug>/original-prompt.md` only to verify that no explicit request was silently discarded. Proposed mechanisms that the combined discovery gate omitted or replaced are not coverage requirements unless the user approved them. Verify every approved Key Requirement or project outcome is covered by at least one chunk's acceptance criteria, and every chunk maps back to one or more approved entries:

```
Requirements Coverage:
  1. [Requirement text] -> chunk-02a (acceptance criterion #3)
  2. [Requirement text] -> chunk-03 (acceptance criterion #1)
  3. [Requirement text] -> NOT COVERED -- adding to chunk-04
```

If any requirement is uncovered, either add it to an existing chunk's acceptance criteria or create a new chunk. Do not proceed with gaps.

### Phase 6b: Evidence-Based Prompt Completeness Check

Every prompt needs a concrete task, exact modified files, relevant pattern/context, observable acceptance criteria for changed behavior, and exact validation commands. Applicable security, data-integrity, browser/persona, migration, and generated-file gates remain mandatory. Every `renderedSurface: required` chunk gets at least two rendered-impression criteria.

There is no minimum prompt-line or general acceptance-criterion count. Prompt length and criterion count are diagnostics only: a short surgical prompt can pass, and no prompt is expanded solely to meet a count or a sibling average. Remove repetition, derivable context, duplicated validation, and criteria that do not map to a requirement or realistic failure mode.

**Commit text guidance for chunk prompts:** when instructing subagents to summarize verification in commit messages, use phrases such as "module build/tests pass in Docker" or "Docker-backed verification passed". Avoid literal bare command phrases like `go build ./...`, `go test ./...`, or `vet` in commit prose because some projects use hooks that block bare-Go claims outside Docker.

**Sibling comparison (advisory evidence check):** group prompts by classification, compute the average line count and AC count per group, and inspect outliers only for a concrete missing requirement, failure mode, or necessary context. Relative size alone is never under-specification or a blocker. A `renderedSurface: required` chunk with fewer than two rendered-impression criteria remains incomplete regardless of sibling size.

**Output a completeness summary** listing each chunk as PASS or BLOCKER with the named gap (e.g., "missing the permission-denial failure mode from REQ-04"), noting when a size diagnostic did not affect the verdict. Fix a blocker by adding the named missing requirement, realistic failure mode, necessary context, applicable gate, or UI rendered-impression criterion -- never text merely to change a diagnostic count. Do not proceed to handoff while a concrete completeness blocker remains.

### Phase 7: Handoff

If running as part of `/pipeline`, pass the manifest to the adversarial review phase. If running standalone via `/pipeline-prompts`, present the manifest summary and prompt list:

```
Generated N prompts for feature "<name>":
  Sequential: [chunks that must run in order]
  Parallel groups: [groups of chunks that can run simultaneously]
  Estimated overlap risk: low/medium/high
  Requirements covered: N/N from approved Key Requirements

Manifest: plans/<feature-slug>/manifest.json
Prompts: plans/<feature-slug>/prompts/
Original: plans/<feature-slug>/original-prompt.md
```
