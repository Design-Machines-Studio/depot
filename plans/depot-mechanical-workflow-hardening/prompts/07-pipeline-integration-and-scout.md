# Chunk: Pipeline Integration and Upstream Improvement Scout

## Context

This is Chunk 07 of Depot Mechanical Workflow Hardening. Chunks 01–06 provide
neutral repository planning, exact build bindings, artifact safety, browser
bundles, structured review records, CI/closeout facts, and the Assembly profile.
This chunk makes Pipeline and dm-review consume those facts in shadow-first mode
and adds the every-run, proposal-only Upstream Improvement Scout.

The workflow remains authoritative in its existing Markdown contracts and
receipts until parity is demonstrated. Kernel code establishes facts and renders
deterministic views; agents retain risk, quality, prioritization, and merge
judgment. The Scout must not become another scheduler, reviewer, or release tool.

## Task

Implement a two-stage Upstream Improvement Scout and integrate all new mechanical
contracts into Pipeline/dm-review orchestration:

1. Before cleanup, seal a redaction-safe index of evidence that cleanup may remove.
2. Run existing exact-owned Docker, artifact, and Git cleanup.
3. Write the authoritative terminal receipt and capture shadow comparison/metrics.
4. Finalize structured improvement candidates using the sealed index plus exact
   cleanup/parity/metric outcomes.
5. Deterministically render a reusable upstream Pipeline prompt from the
   structured candidate report.

The Scout runs on every full Pipeline run, including clean runs. Empty output is
valid. Candidate generation remains proposal-only and cannot mutate upstream
plugin sources, current findings, routing, release, issue, or merge state.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/improvements.py` | Create | Input index, candidate/report validation, dedupe, deterministic prompt renderer |
| `plugins/workflow-kernel/skills/workflow-kernel/references/improvement-input-index-schema.json` | Create | Strict safe pre-cleanup evidence index |
| `plugins/workflow-kernel/skills/workflow-kernel/references/improvement-report-schema.json` | Create | Strict candidates, empty report, recurrence/dedupe/provenance |
| `tests/test_improvements.py` | Create | Evidence, dedupe, empty, recurrence, prompt rendering, hostile input |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py` | Modify | Accept new artifact refs/stages without scheduling authority |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/dm_review_adapter.py` | Modify | Carry structured review/browser/CI refs into terminal evidence |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/_translation.py` | Modify | Add bounded aliases/fields shared by new receipts |
| `tests/test_pipeline_adapter.py` | Modify | New observation stages, legacy/default provenance, parity |
| `tests/test_dm_review_adapter.py` | Modify | New reference continuity and read-only boundary receipts |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Modify | Planner/binding/allowlist/bundle/CI/closeout integration and Scout ordering |
| `plugins/pipeline/commands/pipeline.md` | Modify | Public full workflow, gates, Scout output and delivery summary |
| `plugins/pipeline/commands/pipeline-run.md` | Modify | Codex-native/full-CLI execution adapter parity |
| `plugins/pipeline/references/artifact-lifecycle.md` | Modify | Class/sensitivity, Scout input/output retention, exact allowlist rules |
| `plugins/pipeline/references/run-postmortem-schema.md` | Modify | Measured inputs and separation from Scout candidates |

Do not modify Kernel CLI registration, package exports, exact schema/command
inventories, plugin manifests/versions, root marketplace data, generated Codex
aliases/manifests, Assembly profile files, or dm-review command sources. Chunk 08
owns cross-plugin release integration and generation.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/repository_verification.py` | Planner/profile/result contracts from Chunk 01 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/evidence_binding.py` | Exact build/evidence invalidation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/artifacts.py` | Safe input classification and staging allowlist |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_bundle.py` | Shared immutable browser runtime evidence |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/review_records.py` | Incremental finding/lane records |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/ci_evidence.py` | Provider-neutral CI state and authority |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/closeout.py` | Pure PR/issue closeout facts |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Current authoritative stage order, cleanup, Codify, postmortem, metrics |
| `plugins/pipeline/references/run-postmortem-schema.md` | Existing economics/recommendation data |
| `plugins/pipeline/references/artifact-lifecycle.md` | Existing Tier 1/2/3 retention policy |
| `docs/pipeline-metrics/ledger.md` | Recurrence and measured-run evidence source |
| `plans/adaptive-fusion-verification/run-postmortem.md` | Prior provider attempts, missing telemetry, recommendations |
| `docs/post-mortems/2026-04-10-pipeline-visual-testing-postmortem.md` | Prior applied browser/verification controls to dedupe |

## Patterns to Follow

### Existing workflow authority

- The Progress Ledger, manifest, routing policy, orchestration contracts, and
  authoritative receipts remain the source of truth.
- Kernel observation cannot select ready nodes, advance gates, approve merges,
  change provider fallback, invoke cleanup, or convert review outcomes.
- Exit `5` is a visible parity gap, not a pipeline failure.
- Exact Docker cleanup uses registry-issued plans/outcomes and never prune, glob,
  negative filters, or name-only ownership.
- Run postmortems report measured provider split and unavailable telemetry
  honestly; recommendations remain awaiting approval.

### Planner integration

At preflight, resolve the project profile through the approved precedence and
derive one exact verification plan from repository state, changed paths, declared
risk inputs, and expected authority. Persist profile/plan digests and selected/
omitted lane reasons in authoritative receipts. A missing or invalid explicit
profile is blocking/unavailable, not permission to run guessed commands.

Recompute or invalidate evidence when the relevant exact binding changes after:

- source or generated-file mutation;
- rebase, merge, commit, reset, or working-tree change;
- profile, scenario, or selected-command revision;
- build binary/image change;
- browser scenario/profile change;
- review fix or simplification mutation;
- CI subject or PR head change.

Invalidate only dependent evidence. A documentation-only change need not erase
an unrelated immutable browser bundle unless its binding policy says it affects
the rendered/runtime surface.

### Review and browser integration

- Append structured finding/lane references as they complete.
- Generate reports from structured authority.
- Plain dm-review remains product/Git/provider read-only.
- Capture runtime evidence once per exact scenario/build bundle.
- Fan the bundle out to accessibility, visual, UX, and domain interpretation.
- Re-drive a live browser only when a reviewer requires an unrecorded interaction
  or the exact binding is stale.
- Preserve the full quit/fresh-primary/different-engine/help ladder.
- Never accept curl as browser proof.

### Artifact and staging integration

Classify every generated, downloaded, browser, log, receipt, prompt, manifest,
and report artifact by lifecycle and sensitivity. Redact before promotion and
before Scout indexing. Generate an exact staging allowlist from intended changes
and committable records. Preserve exact deleted/renamed paths. Broad directory,
repository-wide, wildcard, and implicit recursive staging are not authority.

### CI and closeout integration

- Capture normalized CI snapshots with raw provider state and exact subject.
- Keep PR, push, schedule, merge-group, and post-merge evidence separate.
- Derive provider-policy acceptance only from current declared requirements.
- Leave Blueprint authority unresolved without an installed explicit mapping.
- Reconcile exact local/reviewed/delivered/PR head, draft state, required evidence,
  scope, findings, issue entities, closing linkage, and actual closure.
- Closeout evaluation is evidence only; this chunk must not autonomously change
  PR draft state, issues, labels, comments, or merge state.

## Upstream Improvement Scout Contract

### Stage A: seal safe input index before cleanup

Run after implementation, chunk evaluation, final dm-review, requirements
crosscheck inputs, Codify, and run postmortem evidence exist, but before Step 5b
deletes or moves ephemeral/run-scoped files.

The input index includes only artifact-classifier-approved safe references and
digests for evidence such as:

- deterministic validator failures and repeated guardrail trips;
- retry, replacement-builder, convergence, or browser recovery events;
- review coverage gaps and partial/dead lane records;
- repeated setup or command-selection receipts;
- provider requested/attempted/implemented/fallback records;
- missing usage, cost, typed-wait, or authority telemetry;
- existing Codify proposals and postmortem recommendations;
- previously completed, superseded, or standing recommendations;
- selected/omitted verification lanes and reasons;
- known cleanup ownership records that will be finalized later.

Each input record carries stable evidence ID, safe artifact reference, digest,
source run/stage/chunk, observation category, timestamp, classification rule,
and availability. It contains no raw secret/private evidence and no speculative
benefit claim.

Seal the index content-addressably. Cleanup may remove source artifacts only
under existing lifecycle rules; it never rewrites the sealed index.

### Stage B: finalize after cleanup and terminal metrics

After exact Docker reconciliation, artifact/Git cleanup, authoritative terminal
receipt, and captured shadow comparison/metrics, add exact outcomes:

- Docker resources created/removed/missing/retained/blocked/uninspectable;
- artifacts removed/retained/blocked by tier and sensitivity;
- worktrees/branches removed/retained/blocked with merge proof;
- shadow availability/category/reasons and missing authority;
- measured duration, wait, attempt, provider, contribution, and usage values;
- explicit unavailable telemetry rather than zero substitutes.

Then validate and deduplicate candidate proposals. Candidate categories are:

- `new_deterministic_check`;
- `existing_check_repair`;
- `plugin_contract`;
- `telemetry_gap`;
- `depot_architecture`;
- `documentation_or_runbook`.

Every candidate must contain:

- stable candidate ID and category;
- concise observed problem and direct evidence references;
- source runs/stages/chunks and recurrence count;
- status: one-off, recurring, standing, completed, superseded, or rejected;
- dedupe key/reason and links to existing controls/recommendations;
- proposed owner plugin and target files/surfaces;
- mechanical work that could move into code;
- judgment that must remain agent/human-owned;
- proposed acceptance tests/validator evidence;
- confidence grounded in evidence availability;
- safety/authority boundary and compatibility notes;
- expected benefit stated qualitatively unless measured data exists;
- no merge/release authority.

Completed or superseded controls remain represented for dedupe but are omitted
from the generated implementation prompt. A one-run observation may be proposed
with honest recurrence `1`; it must not be called standing. The existing three-
run standing threshold remains recognizable.

An empty candidate array with explicit inspected inputs, dedupe counts, and
reason `no_evidence_backed_improvement` is a valid successful report.

### Deterministic prompt projection

Render `plans/<feature-slug>/upstream-improvement-prompt.md` only from eligible
structured candidates. The prompt includes target Depot repository, preserved
evidence references, bounded scope, proposed files, acceptance tests, compatibility
fences, no invented savings, full `/pipeline` instruction, no release/cache
mutation, and a fresh-review boundary. Editing the Markdown does not mutate the
JSON authority.

The authoritative report path is
`plans/<feature-slug>/upstream-improvements.json`. Both report and generated prompt
are feature-scoped handoff artifacts retained with an open draft PR.

## Relationship to Existing Learning Steps

- Codify remains friction-triggered and focuses on immediate workflow learning.
- The run postmortem remains mandatory and measures provider/economics/reliability.
- The Scout runs every time and identifies evidence-backed upstream code/plugin
  opportunities after terminal outcomes are known.
- The Scout may cite Codify/postmortem outputs but never replaces or mutates them.
- No candidate automatically changes `CLAUDE.md`, a plugin, routing policy, issue,
  release, marketplace, installed cache, or future workflow requirement.

## Companion Skills

Load `pipeline:pipeline-run` for the Codex-native execution contract,
`dm-review:review` for structured review evidence, and `ned:codify` only to keep
the existing friction-triggered boundary distinct from the every-run Scout.

## Acceptance Criteria

- [ ] Pipeline derives and receipts an exact project verification plan before dispatch; invalid/missing explicit profiles remain blocking/unavailable and never trigger guessed commands.
- [ ] Verification/review/browser/CI evidence references exact build/profile/plan/scenario state and is invalidated with specific reasons after relevant changes.
- [ ] Structured findings are recorded incrementally and reports are generated views; plain review remains read-only for product, Git, PR/issue, and tracking state.
- [ ] Browser runtime evidence is captured once per current exact bundle and shared across independent interpretation lanes; stale/unrecorded cases re-run through the full recovery ladder.
- [ ] Artifact classification occurs before durable promotion or Scout indexing, and secret/private content never enters the safe index or generated prompt.
- [ ] Staging uses only the generated exact allowlist, including explicit deletion/rename handling; broad directory/repository/glob staging is absent.
- [ ] CI receipts preserve raw provider state and exact scope/SHA/app authority; PR, push, schedule, merge-group, and post-merge lanes remain non-interchangeable.
- [ ] Blueprint remains unresolved unless an explicit adapter mapping/capability record is present.
- [ ] Closeout compares actual PR head/draft, local/reviewed/delivered SHA, required evidence, claimed scope, findings, parsed/provider issue references, and actual closure without mutation.
- [ ] Stage A seals a deterministic redaction-safe input index after review/postmortem evidence exists and before cleanup can remove eligible sources.
- [ ] Stage B runs after Docker/artifact/Git cleanup, terminal receipt, and captured parity/metrics outcomes, and incorporates exact cleanup results.
- [ ] Scout candidate schema requires direct evidence, recurrence, dedupe, owner/target, acceptance tests, confidence, safety boundary, compatibility, qualitative/measured benefit, and agent-owned judgment.
- [ ] Completed, superseded, rejected, one-off, recurring, and standing states are distinct; completed controls do not reappear as fresh prompt work.
- [ ] Empty candidate output is valid, deterministic, and reports inspected/deduped evidence rather than manufacturing work.
- [ ] The upstream Markdown prompt is deterministically rendered from eligible JSON candidates and cannot become a competing authority.
- [ ] Scout runs every full Pipeline run, including clean runs, but remains proposal-only and cannot change sources, routing, requirements, findings, PR/issues, releases, marketplaces, caches, or merge authority.
- [ ] Codify remains friction-triggered and postmortem remains economics/reliability-focused; neither is silently replaced by the Scout.
- [ ] Missing token/cost/wait/cleanup telemetry remains `unavailable` and never becomes zero or an estimated savings claim.
- [ ] Adapter receipts preserve existing workflow class, execution mode, provider attempt/fallback, decision profile, browser recovery, contribution, cleanup, and shadow-parity semantics.
- [ ] Legacy manifests/runs without new references translate with explicit default/unavailable provenance and current behavior.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_improvements tests.test_pipeline_adapter tests.test_dm_review_adapter tests.test_shadow_parity tests.test_metrics`.
- [ ] Deterministic prose/contract tests prove Stage A precedes cleanup and Stage B follows terminal cleanup/parity evidence in both full-CLI and Codex-native commands.
- [ ] No CLI registry, plugin manifest/version, marketplace, generated alias, or installed cache changes occur in this chunk.
- [ ] `git diff --check` passes and only declared files changed.

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` Sprint Contract Negotiation (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify the files listed above.
- Keep Workflow Kernel standard-library-only and observation-only.
- Preserve the authoritative Pipeline stage order and existing cleanup safety; add the two Scout stages at explicit safe boundaries.
- Never execute cleanup argv outside the existing guarded Kernel execution boundary.
- Never broaden Docker ownership beyond exact repository scope, run ID, node ID, labels, fresh inventory, and dependency proof.
- Never let decision profile, verification selection, provider fallback, or Scout output change security routing or merge authority.
- Never persist or delegate credential values, cookies, private browser content, environment values, or unsafe artifact excerpts.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Prior Depot runs repeatedly lacked durable Codex token/cost and typed-wait data.
PR #12 added complete provider attempt receipts, so the Scout must recognize that
recommendation as completed rather than re-propose it. Browser recovery controls
were also applied after April failures. Current evidence supports one-run
candidates for canonical verification launch commands and separating live sibling
declarations from Depot-owned release gates, but does not prove savings. Both
inspected Depot runs created zero Docker resources, so no Docker cleanup savings
claim is currently supportable.

