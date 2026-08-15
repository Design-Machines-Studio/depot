---
name: promptcraft
description: Self-contained execution prompts and a manifest from a plan, with overlap-aware dependency ordering for parallel vs sequential worktree execution. Use when breaking a plan into executable chunks for autonomous worktree-based execution. Invoke with /pipeline-prompts or as part of /pipeline.
---

# Execution Prompt Generator

Transform a plan into self-contained execution prompts with overlap-aware dependency ordering. Produces a manifest that the execution-orchestrator consumes directly.

## Input

1. **Plan file** -- A pipeline `plan.html` carrying a `#pipeline-data` JSON island (`chunks`, `decisions`, `requirementsCoverage`). When invoked standalone on a hand-written markdown plan, parse the prose directly; within `/pipeline` the plan is HTML.
2. **Original prompt** -- The user's verbatim input saved at `plans/<feature-slug>/original-prompt.md` (stays markdown; requested mechanisms are not automatically approved scope)
3. **Research Brief** (optional) -- `research.html` from the research skill
4. **Assessment Brief** (required within `/pipeline`) -- `assessment.html` from
   the assess skill. Its `keyRequirements` island is authoritative only after
   the combined discovery response; its rendered Project Alignment section is
   the compact source for goal, non-goals, constraints, and ownership.

## Process

### Phase 0: Artifact Format Policy

Pipeline planning artifacts (`assessment`, `research`, `brainstorm`, `plan`) are **HTML carrying a JSON data island**, not markdown. Read their structured data with the island extractor rather than grepping rendered prose:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/extract-json-island.sh" plans/<feature-slug>/plan.html
```

The plan island's `chunks` array seeds Phase 1 decomposition; each chunk's `n` + `slug` map 1:1 onto the `prompts/NN-<slug>.md` you write in Phase 4 (the assembly-baseplate chunk-prompt convention). The assessment island's `keyRequirements` is the cached requirements source for the Phase 6 coverage check. The execution prompts and `manifest.json` you generate stay **markdown/JSON** -- they are agent-only handoffs, not human-facing artifacts. See `references/templates/README.md`.

### Phase 1: Plan Decomposition

Read the plan and identify discrete chunks of work. A chunk is:
- A logically complete unit (one feature aspect, one migration, one component)
- Implementable without needing to see intermediate results of other chunks
- Testable in isolation (has its own acceptance criteria)

**Decomposition rules:**
0. Before chunking, require the plan prose to state the current project goal,
   why the work is appropriate now, explicit non-goals, and the **Smallest
   Usable Implementation**. Every chunk must map through the existing
   requirements-coverage map to at least one approved requirement or project
   outcome. For every proposed new abstraction, service, policy layer,
   background process, cache, transaction ledger, approval ceremony, receipt
   family, compatibility layer, or generalized extension point, the plan must
   name its current consumer, a concrete present failure or realistic reachable
   harm, and what existing mechanism it replaces or why direct code is
   inadequate. Delete unsupported machinery from current scope or retain it
   only as a non-blocking future idea.
1. Database/schema changes are always their own chunk and always run first
2. Backend and frontend work on different files can be separate parallel chunks
3. Integration work (wiring things together) depends on the pieces it connects
4. Test-only chunks are rare -- tests should live with their implementation chunk
5. Configuration/deployment chunks run last
6. Do not create an orchestrator-owned closeout chunk. Verification summaries,
   requirements cross-checks, post-mortems, cleanup, delivery receipts, PR
   publication, and issue disposition belong to the pipeline's final stages.
   They may appear in a product chunk only when that chunk also contains real
   integration code required by its acceptance criteria.
7. After determining `filesToModify` for each chunk, classify its `kind` using the file-extension heuristic:
   - `ui`: any `.templ`, `.twig`, `.html`, `.css`, or files in `pages/`, `templates/`, `views/`
   - `logic`: `.go`, `.py`, `.ts`, `.php` handlers/services/migrations without templates
   - `integration`: prompt contains wiring verbs ("wire," "integrate," "connect") OR modifies route files / `main.go`
   - `config`: `.md`, `.json`, `.yaml`, `.toml`, docs

   Then derive `executor` from the shared routing policy at `plugins/pipeline/references/routing-policy.json`, not from hardcoded local rules:
   - `config` / docs / pure prose -> `openrouter`
   - mechanical `logic` (rename follow-through, test tables, seed/migration edits) -> `openrouter` or `codex` per policy
   - complex `logic` (new service methods, refactors, multi-file behavior) -> `codex`
   - `ui` -> `codex`
   - `integration` -> `codex`

   When a chunk's files span multiple categories, classify up: `ui` > `integration` > `logic` > `config`.

   Then classify rendered-output applicability independently. Every new chunk
   MUST carry `renderedSurface: required|not_applicable` and a non-empty
   `renderedSurfaceRationale`. Use `required` when the chunk changes a served
   route, rendered page/template/component, browser interaction, visible
   output, or visual/browser acceptance criterion. Use `not_applicable` only
   when every UI/integration syntactic trigger is demonstrably unserved or
   non-rendering, such as a planning `.html` artifact or non-HTTP CLI
   `main.go`. Name the triggering files and absence of a product route/output
   in the rationale. Mixed or uncertain chunks are `required`. This field
   controls browser/persona/visual/Datastar evidence only; it never changes
   `kind`, executor routing, or review depth.

   Before assigning Codex because a task needs a live connector, browser, GitHub/Notion operation, or another host-only tool, split the live-tool action from offline analysis/config/docs whenever file ownership and dependency order permit. The offline chunk keeps its policy-selected OpenRouter executor. If a chunk's `executor` differs from the routing-policy default, add a `routingOverride` object with `reasonCode`, a concrete `reason`, `splitAttempted`, and `splitBlockedBy`. A `config`/docs chunk with `executor: codex` and no complete `routingOverride` is invalid; tool mentions alone are never a silent override.

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
`decisionProfile` from the plan island and copy it unchanged. It is a closed
object with exactly `uncertainty`, `consequence`, and `rationale`; the first two
are `low|medium|high` and the rationale is a non-empty string. Extra keys,
malformed values, multiple profiles, or conflict with approved upstream data
blocks prompt generation and returns to the combined discovery gate.

Keep `decisionProfile` distinct from `workflowClass`, `risk`, `overlapRisk`,
`estimatedComplexity`, `kind`, `renderedSurface`, `executor`, and
`routingOverride`. Apply the
`decisionLeverage` section from `routing-policy.json` to workflow depth only:
low/low uses the optimized current path; high uncertainty adds one independent
planning opinion plus one bounded synthesis; high consequence strengthens the
existing independent verification seam; high/high applies both; all other
combinations keep standard depth. Never expand this into debate or full review
per chunk. It cannot select providers/models/executors, relax security, alter
workflow class, reduce browser/persona evidence, weaken cleanup, or alter
economics.

Legacy input with no profile is consumption-only compatibility: keep the
current standard path and record `decision_profile_defaulted=true`. This is
unknown provenance, not low/low evidence. Do not generate a new manifest from
legacy absence. During this bootstrap, an already-generated current manifest
must not be retrofitted even if its approved plan can explain a profile.

### Phase 2: Context Extraction

For each chunk, extract from the plan, research brief, and assessment brief:

1. **Project goal** -- The larger approved goal this chunk serves
2. **Chunk purpose** -- Why this chunk exists and which approved requirement or
   project outcome it addresses
3. **Boundaries** -- Relevant non-goals, ownership boundary, and scope limits
4. **What to build** -- The specific deliverable
5. **File paths** -- Every file the chunk will read or modify
6. **Patterns to follow** -- Existing code patterns from the assessment
7. **References** -- Only research findings relevant to this chunk
8. **Acceptance criteria** -- How to know the chunk is done
9. **Companion skills** -- Which domain plugins to load (assembly, live-wires, etc.)

Do not paste the whole roadmap, assessment, research brief, or Project snapshot
into a prompt. Use the existing Context section and requirement identifiers;
do not introduce a second project-goal identifier system.

Read `references/prompt-template.md` for the exact prompt structure.

### Phase 2.5: Visual Reference Extraction

For chunks with `renderedSurface: required`, check for brainstorm outputs that define the approved visual design:

1. Check `plans/<feature-slug>/brainstorm.html` for visual design decisions -- read the `visualDecisions` island with `references/templates/extract-json-island.sh`
2. Check `.superpowers/brainstorm/` for HTML mockups (these contain styling decisions as inline styles)
3. If found, extract a **Visual Reference Summary**:
   - Key styling decisions (which component variants, which tokens, which layout patterns)
   - Visual hierarchy: what should be prominent, what should be subdued
   - Specific visual treatments called out in the approved design (e.g., "outline variant for destructive actions", "natural-width buttons")
4. Do NOT embed full HTML mockups in prompts -- extract the decisions, not the markup. Full mockups waste token budget and obscure the intent.
5. Include the file PATH to the mockup so the subagent can reference it if needed

This summary feeds into each rendered-surface chunk's prompt as a `## Visual References` section and shapes the visual acceptance criteria in `### Visual Acceptance Criteria`.

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
4. **Automatic zero-caller check:** for every helper, constant, or function defined in a file listed in `filesToModify`, grep the codebase for its callers. If the proposed changes leave it with zero callers, flag as "survivor needs inlining or deletion."

```
Survivor audit:
  base.js (108 lines) -- kept for markdown-editor.js (1 consumer, uses 3 of 10 features)
  VERDICT: Inline the 3 used features into markdown-editor.js, delete base.js
```

### Phase 3e: Stable Anchors Audit

Line numbers are time-bounded. A prompt written in Phase 3 and executed in Phase 6 may see completely different lines if an interstitial chunk edited the file. Prefer stable anchors in all prompt text.

**Anchor hierarchy (prefer the highest-ranking anchor available):**

1. **Function / method names** (Go, Python, TS, PHP): use `grep -n "func <name>" <file>` or `grep -n "def <name>" <file>` as the localization mechanism. Example: "Edit the `SetPosition` handler in `internal/handler/position.go`" beats "Edit lines 42-68 of `internal/handler/position.go`".
2. **Templ / component names** (.templ, .twig, .jsx/.tsx components): use `grep -n "templ <name>" <file>` or `grep -n "<component name>" <file>`. Example: "Amend the `PositionChangeDialog` component in `internal/view/proposal/dialogs.templ`" beats "Amend lines 235-259".
3. **Markdown heading slugs** (documentation cross-refs): link to `#section-name` rather than `docs/foo.md:42`.
4. **SQL table + column** (migrations): reference the migration filename plus the table and column name, e.g. `003_add_votes.sql modifies proposals.vote_count`.

**When line numbers are unavoidable** (unnamed blocks, constants, YAML keys):

- Annotate with `// verified at HEAD <short-sha>` so the reader knows the reference's time window.
- Include a re-verification grep as an acceptance criterion: `AC: lines 42-68 of path/to/file still contain the signature "<unique-string>" at execution time; if the grep fails, the chunk must stop and re-anchor.`

**Enforcement:** when generating prompts, prefer structural anchors. A prompt-wide line-number count above 5 is a smell -- most of those should be function or component names.

### Phase 3f: Migration Numbering Gate

For plans that include database migrations, verify the next sequence number is correct and that schema changes precede dependent handler/service chunks.

**Rule:** Read `ls migrations/*.sql | sort | tail -1` from the target repo to determine the current highest migration number. The plan's migration must use the next sequential number. If two chunks both add migrations, they must be sequentially ordered (not parallel) and use consecutive numbers.

### Phase 3g: Generated Templ Policy

Generated `*_templ.go` files must never appear in `filesToModify` or acceptance criteria. They are build artifacts regenerated by `templ generate`.

**Rule:** Add this constraint to every chunk that modifies `.templ` files: "Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files."

### Phase 3h: Assembly Mutation Applicability Gate

For each Assembly mutation chunk, consult `assembly:development`'s Mutation Applicability Matrix. Record only applicable authorization, validation/invariant, transaction, audit, event, SSE, service-abstraction, and test criteria, each with a one-line reason tied to a present behavior, current consumer/contract, or realistic consequence. Omit inapplicable controls without `N/A` ceremony. A mutation verb or SQL statement alone never proves that every control applies; any required event still publishes strictly after commit.

**Auth Boundary Map gate:** The map is mandatory when a change actually alters authentication, middleware, an Authorizer action/resource, a privileged read/write, a role/member/account/install/module permission, or a privileged UI capability. Path names such as `auth/`, `admin/`, `account/`, `install/`, `member/`, and module-permission paths are review hints, not proof that the boundary changed. The receipt enumerates mapped surfaces, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases addressed, test files, and residual risk. Without this receipt an actual boundary-changing chunk is incomplete.

**Data-integrity receipt (membership and settings chunks):** When a chunk adds, edits, clones, or reorders rows in a membership, settings, or permissions surface, its acceptance criteria must include:

1. **Stable row identity.** Every row carries a server-issued ID. Never an array index, never DOM order, never a client-generated key. Reordering or filtering the list must not change which record a mutation targets.
2. **Cloned rows regenerate their ID.** A duplicated row must not inherit the source row's identifier -- the submit then silently overwrites the original.
3. **Validation fails closed.** Unknown fields are rejected, missing required fields are rejected, and a zero-value enum is invalid rather than defaulting to the first option.
4. **Async mutations announce.** Every row-level loading and completion state is announced through a live region, not conveyed by a spinner alone.

### Phase 3i: Visual Acceptance Criteria Gate

Every chunk with `renderedSurface: required` must include at least 2 visual acceptance criteria describing rendered impressions, not just structural class names.

**Rule:** Rendered-surface chunks must have a `### Visual Acceptance Criteria` subsection with >= 2 criteria. "Uses `.button--accent` class" is structural. "Primary action button is visually dominant over secondary actions" is visual. Both types are required. A chunk marked `not_applicable` must not fabricate rendered impressions.

**Shared-component parity:** When one Templ component is rendered on two or more routes -- a shared editor, a shared form, a shared dialog -- the chunk must carry a **Visual Parity Criterion** even when the prompt never says "visually identical". Sharing a component is itself the parity claim, and a route-specific wrapper or a stale override quietly breaks it.

Detect by grepping the plan's `filesToModify` for a component invoked from more than one page package. For each such component, add:

1. `Screenshot of <component> at /route-a and /route-b at the same viewport shows identical rendering.`
2. `getComputedStyle on <selector> matches across both routes for: font-size, font-weight, color, padding, margin, background-color, border.`

Both criteria are **P1**. A shared component that renders differently per route is not polish -- it is the component failing to be shared.

### Phase 3j: UX Task Selection Gate

When the target repo contains `tests/ux/`, reference persona tasks in prompts whose `renderedSurface` is `required`.

**Rule:** If `tests/ux/` exists, each rendered-surface chunk's Research Context must reference which persona tasks cover the affected routes. If no task file exists for a new route, add an acceptance criterion: "Create task file at `tests/ux/tasks/{area}/{task-name}.md`."

Use `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md`.
Carry the complete selected persona/scenario/route/browser/viewport case set into
acceptance criteria for chunks with `renderedSurface: required`. Task frontmatter is authoritative; do
not turn the generated coverage matrix or a fixed persona sample into coverage.
Required browser criteria must preserve the evidence -> primary process quit ->
fresh primary relaunch/retry -> different engine -> `human_help_required` ladder.
Curl/reachability never satisfies browser evidence.

### Phase 3k: Parallel Prompt Isolation Gate

Sibling parallel prompts must not cross-reference each other. A prompt in a parallel group that says "after chunk-02 adds the handler" is broken if chunk-02 runs concurrently.

**Rule:** For each parallel group, grep prompt text for references to sibling chunk IDs. Any cross-reference is a BLOCKER -- restructure as sequential dependency or inline the referenced context.

### Phase 3l: Manifest Schema Conformance Gate

Validate the generated manifest against the required schema before handoff.

**Rule:** Every chunk object in the authoritative `chunks[]` array must include: `id`, `title`, `prompt`, `kind`, `renderedSurface`, `renderedSurfaceRationale`, `executor`, `filesToModify`, `dependsOn`, `companionSkills`, `estimatedComplexity`. Missing fields cause orchestrator dispatch failures. `renderedSurface` accepts only `required|not_applicable`; its rationale must be non-empty, and `not_applicable` must account for every UI/integration syntactic trigger. When the selected executor differs from the routing-policy default, `routingOverride` is also required and must include `splitAttempted`; omit the object when no override occurred.

Every new manifest also carries the explicit top-level `workflowClass` copied unchanged from the approved plan island. Accepted values are `chore|bug|feature|hotfix|security|investigation|migration`. If the plan does not contain exactly one approved value, stop and return to the combined discovery gate; promptcraft never chooses or infers it from filenames, chunk kinds, prompt prose, risk, or keyword heuristics. The legacy absent-field default belongs only to manifest consumption and records `feature` plus `workflow_class_defaulted=true`.

Every new manifest also carries the exact approved top-level
`decisionProfile`. Validate the closed shape and exact plan/manifest equality;
reject malformed, multiple, extra-key, or conflicting profiles. Never infer it
from `workflowClass`, risk, complexity, kind, executor, or routing data.

Every new manifest also carries the approved branch and final-review controls.
Validate exact plan/manifest equality for `branchMode`,
`expectedFeatureHead`, `finalReviewMode`, and `finalReviewRationale`.
`branchMode: reuse` requires exact remote-head hex and forbids the create-mode
initial push; `create` requires the expected head to be null/absent.
`finalReviewMode: quick` requires explicit approval, non-high consequence, and
a proportionate rationale; security-sensitive final diffs still escalate to
full. These controls never weaken per-chunk review or verification.

### Phase 3l.5: Behavioral Contract Readiness Gate

Prepare deterministic contract inputs from the approved Key Requirements and
the final acceptance criteria. Assign stable `REQ-*` and `CHK-*` IDs, preserve
explicit prohibited regressions, and classify every requirement as executable
or manual per
`plugins/workflow-kernel/skills/workflow-kernel/references/behavioral-verification-contract-schema.json`.
For work with `renderedSurface: required`, resolve selected persona and browser case IDs from the
authoritative declarations described by `verification-contract.md`; generated
coverage matrices and invented sample personas are not authority. Any unresolved
persona, scenario, route binding, browser, viewport, auth fixture, or case ID
blocks handoff.

For validated `renderedSurface: not_applicable` chunks, contribute no persona or
browser case IDs to the run-wide contract and preserve the rationale in the
manifest and receipts. If the run has zero `required` chunks, use the contract's
explicit no-profile/null pair and empty case arrays; otherwise the bound profile
and arrays contain only the union selected for `required` chunks. Do not create
placeholder cases, fake routes, or `not_declared` browser evidence to satisfy a
kind-based heuristic.

Promptcraft does not bind or pre-authorize the contract. The execution
orchestrator generates the canonical JSON from these approved inputs only after
`run.started`, then validates and binds it before the first builder dispatch.
Every dispatch and builder completion must echo the current contract digest and
revision exactly.

Repository verification evidence stays bounded across model prompts. A passing current-invocation result appears once as selected check IDs, status, and plan digest; raw passing stdout/stderr and repeated result copies never enter builder repair or reviewer prompts. Before model review, a failure reaches the repair attempt as bounded canonical failing check IDs, a stable failure signature, and a trusted profile-derived reproduction instruction. Never include raw logs, secrets, environment, arbitrary host paths, or unbounded output.

### Phase 3m: Fixture SDK Conformance Gate

**Trigger:** the chunk touches `internal/fixtures/`, the `Module` interface, or a fixture SDK path.

The SDK's guarantees are only real if something tries to break them. Every such chunk carries **negative-test** acceptance criteria -- proof the invalid case is rejected, not just that the valid case works. "The SDK validates it" is an assertion; the rejected input is the evidence.

**Rule:** the prompt must include an acceptance criterion for each invariant the chunk touches, written as the negative case:

| Invariant | Required AC (negative form) |
|---|---|
| Table-prefix enforcement | An unprefixed table name, or another fixture's prefix, is rejected by `ScopedDB` |
| Zero-value auth | A zero-value `Authorizer` or nil/zero actor **denies**. An uninitialized auth struct never allows |
| Stream subject validation | A subject outside the fixture's own prefix is rejected at registration |
| Reserved scopes | Registering under `gov`, `doc`, `eq`, `health`, `member`, `system`, `audit`, or `federation` from a fixture that does not own that scope is rejected |
| Disabled-module route leakage | A disabled fixture's routes return 404 -- not 200, not 500, not a redirect |
| Module lifecycle | `register -> enable -> disable -> teardown` runs clean, and a second `enable` reattaches routes and streams |
| All-or-nothing stream preflight | A stream set with one invalid subject registers **none** of them |

Plus: **a new case is added to the conformance harness in the same chunk.** A harness that only exercises the happy path proves nothing.

Fail-closed is the theme. Any invariant that defaults to permissive on absent input (zero value, empty string, unset flag, missing module) is a P1 and the prompt says so.

### Phase 3n: Production Readiness Preflight Gate

**Trigger:** the chunk touches config loading, the updater, release tooling, shutdown, or key rotation.

**Rule:** the prompt must carry acceptance criteria for each applicable item:

1. **Config validation is fail-closed at boot.** Invalid config exits non-zero. It never defaults through, never warns and continues.
2. **Update candidate is preflighted before replacement.** Checksum, signature, and version ordering are verified against the *candidate* before any file is swapped. A "verified" claim with no actual verify call is a BLOCKER.
3. **Update-failure recovery copy is actionable.** The message names the recovery command, not "an error occurred".
4. **Shutdown ordering is explicit.** Drain HTTP -> stop consumers -> flush -> close DB. An unordered `defer` stack is not a shutdown sequence.
5. **Key rotation covers both sides.** Email and federation key checks are fair on the responder side (a rotated key is detected, not silently rejected as forged) and old keys have a stated grace window.
6. **Critical forms are double-submit protected server-side.** An idempotency token, not a disabled button. Repair and recovery forms especially -- they run when the system is already unhealthy.
7. **A release receipt exists**, enumerating active-install monitoring and beta-finalization proof.
8. **Runbooks and docs are updated in the same chunk**, not deferred to a follow-up.

### Phase 3o: Datastar-First Gate

**Trigger:** the project is Go + Templ + Datastar and the chunk has `renderedSurface: required`.

Agents reach for hand-rolled JS by default. Most client behavior an Assembly page needs already exists as a declarative Datastar attribute, and a Datastar Pro attribute whose plugin is missing from the bundle is **inert** -- a silent no-op that looks correct in review.

**Rule:** the prompt must

1. **Name the attribute per interaction.** For each interactive behavior, state which Datastar attribute or action implements it (`data-persist`, `data-query-string__history`, `data-match-media:signal`, `@clipboard`, `@intl`, ...). See the substitution table in `plugins/assembly/skills/development/datastar-pro.md`.
2. **Carry a bundle-presence check** for every Pro attribute it prescribes -- a grep of the vendored bundle for the plugin's **registered name** (`grep -c "'query-string'" web/static/vendor/datastar.js`), not for the `data-` attribute. If the plugin is absent, the chunk either adds "regenerate the bundle including `<plugin>`" as an explicit step, or falls back to the free tier. Prescribing a Pro attribute into a bundle that lacks it is a BLOCKER.
3. **Include the no-new-JS acceptance criterion:** "No new `<script>` block or `.js` file is introduced. If one is unavoidable, the prompt names the interaction and states why the substitution table has no entry for it."
4. **List `assembly:development` in `companionSkills`** so the substitution table travels with the prompt (the Phase 5 companion-skills check already requires this for Assembly chunks; this gate makes the reason explicit).

### Phase 4: Prompt Generation

For each chunk, generate a self-contained execution prompt using the template from `references/prompt-template.md`. Each prompt must be:

1. **Self-contained** -- All context inlined, no external references needed
2. **Specific** -- Exact file paths, exact patterns to follow, exact acceptance criteria
3. **Scoped** -- Only touches the files listed, nothing else
4. **Testable** -- Clear acceptance criteria the subagent can verify
5. **Visually specified** (`renderedSurface: required`) -- Include the Visual Reference Summary from Phase 2.5 and generate both structural AND visual acceptance criteria (see prompt template)
6. **Project-aligned** -- Its Context names the larger project goal, why the
   chunk exists, the approved requirement or outcome it addresses, and only the
   relevant non-goals and ownership boundary

Write each prompt to `plans/<feature-slug>/prompts/<chunk-id>.md`, where `<chunk-id>` is the `NN-<slug>` from the plan island's `chunks` (zero-padded, ordered; e.g. `00-preflight`, `01-reader-service`, ... `10-doc-sync`). Prompts stay **markdown** -- they are Tier 2 (run-scoped) agent-only artifacts, auto-deleted by the orchestrator's cleanup phase after successful execution.

### Phase 5: Manifest Generation

Generate `plans/<feature-slug>/manifest.json` following the schema in `references/manifest-schema.md`. The manifest is a Tier 2 (run-scoped) artifact -- auto-deleted after successful execution.

Read top-level `workflowClass`, the exact closed `decisionProfile`,
`branchMode`, `expectedFeatureHead`, `finalReviewMode`, and
`finalReviewRationale` from the approved plan data island. Copy them explicitly
into every generated manifest and preserve those exact values through handoff.
Missing, ambiguous, malformed, multiple, or conflicting plan data blocks
generation and returns to the user gate. New plans use `branchMode:
create|reuse`; `reuse` requires an exact lowercase 40- or 64-hex
`expectedFeatureHead`, while `create` requires it to be null or absent. New
plans use `finalReviewMode: full|quick` with a non-empty rationale. `quick`
requires explicit plan approval and is invalid for `decisionProfile.consequence:
high`; a final security-sensitive path match still escalates to full. These
fields never weaken per-chunk sensitive review, repository/browser evidence,
zero-deferral, or cleanup.

Each chunk object in the manifest MUST include `kind`, `renderedSurface`, `renderedSurfaceRationale`, and `executor` fields (classified independently in Phase 1, step 7). Example:

```json
{
  "id": "01-database-migration",
  "title": "Add vote columns to proposals table",
  "prompt": "prompts/01-database-migration.md",
  "level": 0,
  "parallelGroup": null,
  "dependsOn": [],
  "filesToModify": ["internal/database/migrations/003_add_votes.sql"],
  "companionSkills": ["assembly:development"],
  "estimatedComplexity": "small",
  "kind": "logic",
  "renderedSurface": "not_applicable",
  "renderedSurfaceRationale": "The migration changes storage only and exposes no product route or rendered output.",
  "executor": "openrouter"
}
```

If the example were forced from its default OpenRouter rail to Codex for an inseparable live-tool requirement, it would also carry:

```json
"routingOverride": {
  "reasonCode": "required-live-tool",
  "reason": "The same atomic file edit must be verified through the authenticated connector.",
  "splitAttempted": true,
  "splitBlockedBy": "The connector result determines the exact value written to this file."
}
```

The manifest encodes:
- Chunk ordering and dependencies
- Parallel groups
- Overlap analysis results
- Feature branch naming
- Branch creation or exact-head reuse semantics
- Execution metadata
- Workflow class for trusted kernel policy translation
- Approved decision profile for depth-only planning and verification leverage
- Approved full-or-quick final dm-review mode and rationale
- Explicit rendered-surface applicability for visual/browser evidence

### Phase 6: Requirements Coverage Check

Read the approved Key Requirements from the `keyRequirements` island of `plans/<feature-slug>/assessment.html` (`extract-json-island.sh`), re-reading `plans/<feature-slug>/original-prompt.md` only to verify that no explicit request was silently discarded. Proposed mechanisms that the combined discovery gate omitted or replaced are not coverage requirements unless the user approved them. Verify every approved Key Requirement or project outcome is covered by at least one chunk's acceptance criteria, and every chunk maps back to one or more approved entries. Produce a coverage map:

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

**Commit text guidance for chunk prompts:** When instructing subagents to summarize verification in commit messages, use phrases such as "module build/tests pass in Docker" or "Docker-backed verification passed". Avoid literal bare command phrases like `go build ./...`, `go test ./...`, or `vet` in commit prose because some projects use hooks that block bare-Go claims outside Docker.

**Sibling comparison (advisory evidence check):**

1. Group prompts by classification.
2. For each group, compute the average line count and AC count.
3. Inspect outliers only for a concrete missing requirement, failure mode, or necessary context. Relative size alone is never under-specification or a blocker.
4. A `renderedSurface: required` chunk with fewer than two rendered-impression criteria remains incomplete regardless of sibling size.

**Output a completeness summary:**

```text
Prompt Completeness:
  chunk-01: PASS -- task, files, context, mapped requirements, failure modes, validation, and 2 rendered impressions present
  chunk-02: BLOCKER -- missing the named permission-denial failure mode from REQ-04
  chunk-03: BLOCKER -- generated-file gate applies, but the prompt does not name the source file or regeneration command
  Diagnostics: chunk-03 is shorter than its siblings; size did not affect the verdict
```

Fix a blocker by adding the named missing requirement, realistic failure mode,
necessary context, applicable gate, or UI rendered-impression criterion. Do not
add text merely to change a diagnostic count. Do not proceed to handoff while a
concrete completeness blocker remains.

### Phase 7: Handoff

If running as part of `/pipeline`, pass the manifest to the adversarial review phase. If running standalone via `/pipeline-prompts`, present the manifest summary and prompt list to the user.

Present a summary:

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
