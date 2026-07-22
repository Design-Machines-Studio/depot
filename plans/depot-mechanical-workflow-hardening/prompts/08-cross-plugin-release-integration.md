# Chunk: Cross-Plugin Release Integration

## Context

This is Chunk 08, the final product-integration chunk of Depot Mechanical
Workflow Hardening. Chunks 01–07 implement the bounded contracts and consumer
behavior. This chunk makes the complete surface releasable inside the repository:
stable CLI commands, package exports, receipt stages, exact inventories, plugin
dependency floors, canonical documentation, generated Codex adapters, fixtures,
and full validation.

This is an unpublished release integration. Do not tag, publish, refresh a
marketplace, update installed caches, merge, or make the draft PR ready. The
Pipeline orchestrator owns final crosscheck, cleanup, delivery receipt, PR
publication, and the fresh independent dm-review prompt after chunks finish.

## Task

Wire every approved contract through the sanctioned Workflow Kernel CLI and
cross-plugin release surfaces. Update exact schema/command inventories and
compatibility fixtures. Apply coordinated canonical version/dependency changes,
regenerate all derived Codex artifacts, synchronize documentation, and run the
full Depot validation matrix.

Use these unpublished versions:

- Workflow Kernel `0.4.0`;
- Assembly `3.9.0` with hard Workflow Kernel dependency `>=0.4.0`;
- dm-review `1.46.0` with Workflow Kernel dependency `>=0.4.0`;
- Pipeline `1.33.0` with dm-review `>=1.46.0`, Workflow Kernel `>=0.4.0`, and
  Assembly optional floor updated when required by the Baseplate profile contract.

## Files to Modify

| File or surface | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Modify | Stable schema-validating subcommands and safe output/exit behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/__init__.py` | Modify if required | Public contract exports only |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/__main__.py` | Modify only if required | Preserve existing entry-point behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py` | Modify if required | Final stage vocabulary and compatibility after Chunk 07 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/dm_review_adapter.py` | Modify if required | Final review stage vocabulary and compatibility after Chunk 07 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/_translation.py` | Modify if required | Closed receipt aliases/envelope after integration |
| `tests/test_cli.py` | Modify | Direct CLI parsing and success/failure cases |
| `tests/test_runtime_cli.py` | Modify | Real launcher/runtime behavioral cases |
| `tests/test_release_validator.py` | Modify | Exact 22-schema and 35-command inventory if all planned documents/commands ship |
| `tests/test_schema.py` | Modify | All new schema documents and strict matcher cases |
| `tests/test_compatibility.py` | Modify | Legacy/new profile, receipt, adapter, and manifest behavior |
| `tests/test_pipeline_adapter.py` | Modify if required | Final terminal stage and Scout references |
| `tests/test_dm_review_adapter.py` | Modify if required | Final record/browser/CI references |
| `tools/validate-workflow-kernel.py` | Modify | Exact release inventory and behavioral CLI cases |
| `tools/validate-workflow-contracts.sh` | Modify | Cross-plugin read-only/planner/Scout/closeout contracts |
| `tools/check-dependencies.sh` | Modify | Assembly becomes a required Kernel consumer |
| `tools/validate-dual-compat.sh` | Modify only if required | New cache/dependency/alias checks |
| `plugins/workflow-kernel/.claude-plugin/plugin.json` | Modify | Canonical version/description/capability text |
| `plugins/assembly/.claude-plugin/plugin.json` | Modify | Canonical version and hard Kernel dependency |
| `plugins/dm-review/.claude-plugin/plugin.json` | Modify | Canonical version and dependency floor |
| `plugins/pipeline/.claude-plugin/plugin.json` | Modify | Canonical version and dependency floors |
| `.claude-plugin/marketplace.json` | Modify | Canonical marketplace versions only; no publish |
| `CLAUDE.md` | Modify | Canonical architecture, inventories, validation, failure boundaries |
| `plugins/workflow-kernel/skills/workflow-kernel/SKILL.md` | Modify | Public neutral mechanics and CLI inventory summary |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md` | Modify | Planner/runner/result authority and compatibility contract |
| `plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md` | Modify | Exact launcher and runtime resolution for new commands |
| `.agents/plugins/marketplace.json` | Regenerate | Generated from canonical marketplace |
| `plugins/workflow-kernel/.codex-plugin/plugin.json` | Regenerate | Generated from canonical plugin manifest |
| `plugins/assembly/.codex-plugin/plugin.json` | Regenerate | Generated from canonical plugin manifest |
| `plugins/dm-review/.codex-plugin/plugin.json` | Regenerate | Generated from canonical plugin manifest |
| `plugins/pipeline/.codex-plugin/plugin.json` | Regenerate | Generated from canonical plugin manifest |
| `plugins/assembly/skills/assembly-build/SKILL.md` | Regenerate | Generated from `commands/assembly-build.md` |
| `plugins/dm-review/skills/dm-review/SKILL.md` | Regenerate | Generated from `commands/dm-review.md` |
| `plugins/dm-review/skills/dm-review-fix/SKILL.md` | Regenerate | Generated from `commands/dm-review-fix.md` |
| `plugins/dm-review/skills/dm-review-loop/SKILL.md` | Regenerate | Generated from `commands/dm-review-loop.md` |
| `plugins/pipeline/skills/pipeline/SKILL.md` | Regenerate | Generated from `commands/pipeline.md` |
| `plugins/pipeline/skills/pipeline-run/SKILL.md` | Regenerate | Generated from `commands/pipeline-run.md` |

These paths are the exact generated ownership for this chunk. Run both sanctioned
generators in write mode, then compare their changed output to this list. If a
generator touches any additional path, stop under the Ambiguity Protocol and
return for a reviewed manifest replan; do not stage or silently broaden scope.

## Files to Read (for context)

| File | Why |
|------|-----|
| `tools/validate-workflow-kernel.py` | Current exact eight-schema/21-command release gate |
| `tests/test_release_validator.py` | Duplicate exact inventory that must agree |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Existing subparser, input, output, exit-code patterns |
| `plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md` | Sanctioned launcher and compatibility contract |
| `plugins/workflow-kernel/.claude-plugin/plugin.json` | Kernel canonical manifest |
| `plugins/assembly/.claude-plugin/plugin.json` | Assembly canonical manifest/dependencies |
| `plugins/dm-review/.claude-plugin/plugin.json` | dm-review canonical manifest/dependencies |
| `plugins/pipeline/.claude-plugin/plugin.json` | Pipeline canonical manifest/dependencies |
| `.claude-plugin/marketplace.json` | Canonical marketplace version source |
| `tools/generate-codex-manifests.py` | Canonical-to-Codex manifest generator |
| `tools/generate-codex-command-skills.py` | Canonical command-to-skill alias generator |
| `tools/check-dependencies.sh` | Current required Kernel consumer assumptions |
| `tools/validate-composition.sh` | Full release validation ordering |
| `tools/validate-workflow-contracts.sh` | Cross-plugin prose and source invariants |
| `plugins/pipeline/references/routing-policy.json` | Coding provider policy and protected boundaries |
| `plans/depot-mechanical-workflow-hardening/assessment.html` | Baseline gaps and current version inventory |
| `plans/depot-mechanical-workflow-hardening/research.html` | Compatibility and authority decisions |

## Patterns to Follow

### Canonical versus generated sources

- `.claude-plugin/marketplace.json` is canonical; `.agents/plugins/marketplace.json`
  is generated.
- Each `.claude-plugin/plugin.json` is canonical; `.codex-plugin/plugin.json` is
  generated.
- `plugins/<name>/commands/<command>.md` is canonical; generated command-skill
  aliases are regenerated from it.
- Shared skill/agent/reference content is edited once.
- Any new cache resolution includes Claude-first and Codex-fallback roots.

Run generators in write mode after canonical edits, then in `--check` mode after
all changes are stable. Generated diffs must be mechanical and reviewable.

### Stable CLI behavior

Follow existing `argparse` subparser patterns, strict JSON file parsing, bounded
safe errors, atomic output, and stable exit codes:

- `0` success;
- `2` invalid input/schema;
- `3` unsafe/blocked;
- `4` unavailable/incompatible;
- `5` parity gap where applicable;
- `6` write/state conflict.

No CLI command executes an arbitrary shell string or accepts credential values.
Provider/network collection stays in adapters/callers. CLI mechanics validate,
derive, record, compare, audit, or render from explicit files and safe arguments.

Use clear contract-specific commands. The planned public surface is:

1. `verification-plan` — derive a plan from profile/repository/change/risk inputs;
2. `verification-run` — execute one selected still-current local lane via its
   bound safe argv and emit a structured lane result;
3. `verification-result` — validate/record one lane result;
4. `evidence-match` — compare expected/current binding and emit reason codes;
5. `artifact-classify` — classify exact intended artifacts;
6. `staging-allowlist` — derive exact committable path authority;
7. `browser-scenario-validate` — validate scenario/profile/binding inputs;
8. `browser-bundle-record` — validate and seal an immutable bundle;
9. `review-record` — validate/store finding or lane records and event refs;
10. `ci-evidence-normalize` — validate explicit provider mapping/snapshot input;
11. `closeout-audit` — evaluate expected versus observed PR/issue/evidence state;
12. `improvement-index` — seal safe pre-cleanup evidence references;
13. `improvement-finalize` — validate/dedupe terminal candidate report;
14. `improvement-render` — render the reusable upstream prompt from JSON authority.

If implementation evidence proves a different decomposition is materially safer,
use the Ambiguity Protocol and update all source docs, behavioral cases, and exact
inventories together. Do not silently add generic multiplexed commands or omit a
required stable operation merely to preserve the projected count.

Every command needs:

- one successful behavioral release-validator case using real safe fixtures;
- invalid JSON and unknown-key failure;
- missing-file and unsafe-path behavior;
- secret-shaped durable input rejection where applicable;
- output determinism and no raw exception/secret text;
- direct CLI and launcher/runtime test coverage;
- documented input/output schema and stable exit behavior.

### Schema inventory

The current release has eight public schemas. Chunks 01–07 plan fourteen new
independently versioned documents:

- repository verification profile;
- verification plan;
- verification result;
- evidence binding;
- artifact classification;
- staging allowlist;
- browser scenario;
- browser evidence bundle;
- review finding record;
- review lane record;
- CI evidence;
- closeout audit;
- improvement input index;
- improvement report.

If all ship, the exact released inventory is 22 documents. Update both validator
and test expectations from actual files; do not merely change the number. Each
schema must load, resolve local references, reject unknown fields, and match the
runtime model. Do not silently widen an existing schema when a new version-1
document is the safer compatibility boundary.

### Receipt and adapter integration

Update only the stage names and bounded fields actually emitted by Chunks 01–07.
Likely stages include repository verification plan/result, evidence binding,
artifact classification/allowlist, review finding/lane, browser bundle, CI
evidence, closeout audit, improvement input, and improvement report.

Preserve:

- existing workflow class and default provenance;
- execution mode and isolation strategy separation;
- provider requested/attempted/implemented/fallback fields;
- behavioral contract revisions;
- decision profile behavior;
- contribution/economics scope;
- browser recovery and missing cases;
- cleanup ownership/outcomes;
- shadow prediction/observation ordering and semantics.

Do not add all new data to `RunSpec`, expand workflow classes, alter Kernel safety
stages, or let an improvement candidate become workflow authority. Immutable
artifact references/digests in receipts are preferred to embedding large records.

### Dependency and version integration

Assembly now calls the executable planner from standalone build/test guidance,
so `workflow-kernel >=0.4.0` is a hard dependency. Update dependency validation,
which previously recognized only Pipeline and dm-review as required consumers.

dm-review consumes structured record/browser/CI/closeout mechanics and requires
Kernel `>=0.4.0`. Pipeline consumes dm-review's read-only contract and all new
Kernel mechanics, requiring dm-review `>=1.46.0` and Kernel `>=0.4.0`. Raise the
optional Assembly floor to `>=3.9.0` if Pipeline declares compatibility with the
new profile rather than legacy Assembly behavior.

Version descriptions and capabilities should name user-visible behavior without
listing every internal module. No capability should claim live provider support
that fixtures cannot prove. Blueprint remains adapter-defined/unresolved.

### Documentation integration

Update canonical documentation to explain:

- neutral Kernel versus Assembly defaults versus Pipeline/dm-review consumers;
- repository profile precedence and unavailable behavior;
- tiered verification and authority separation;
- exact build/evidence invalidation;
- incremental finding authority and generated Markdown views;
- read-only review versus approved fix/loop mutation;
- shared browser bundle and recovery ladder;
- artifact sensitivity/lifecycle and exact staging allowlists;
- provider-neutral CI with raw/derived separation;
- pure closeout audit and issue-link semantics;
- two-stage every-run proposal-only Improvement Scout;
- measurement limits and intentionally agent-owned judgment;
- migration/legacy defaults and shadow-to-enforcement path.

Avoid copying full schema field lists into multiple docs. Link the canonical schema
or reference document so the surface cannot drift.

## Companion Skills

Load `pipeline:pipeline-run` for execution/receipt compatibility,
`dm-review:review` for final review contracts, and `assembly:assembly-build` for
the standalone Assembly dependency surface. Source files in this branch are the
implementation authority when installed caches differ.

## Acceptance Criteria

- [ ] All fourteen required mechanical operations have stable CLI commands or an explicitly justified safer decomposition recorded through the Ambiguity Protocol.
- [ ] `verification-run` executes only a selected still-current local plan lane, uses bound safe argv without a shell or caller environment values, returns doctor/Go-parser structured results, and has direct CLI/runtime tests for stale bindings, unsafe commands, missing tools/services, timeout, malformed Go JSON, and incomparable coverage baselines.
- [ ] Every new command has a real successful behavioral validator case, direct CLI test, runtime launcher test, invalid/unsafe cases, deterministic output, and documented exit behavior.
- [ ] CLI input is strict JSON/safe argv; no arbitrary shell command, provider credential, environment value, network SDK, or raw private evidence is accepted or emitted.
- [ ] The exact schema inventory contains all existing eight and all actually shipped new documents; validator and release test enumerate identical names.
- [ ] Every new schema resolves, rejects unknown keys, matches runtime objects, remains independently versioned, and preserves explicit legacy/default provenance.
- [ ] Exact CLI command inventory in `tools/validate-workflow-kernel.py` and `tests/test_release_validator.py` matches parser registration; help-only probes do not count.
- [ ] New receipt stages/fields/aliases are bounded, necessary, translation-tested, and preserve all preexisting workflow/economics/browser/cleanup semantics.
- [ ] Legacy manifests, review requests, receipts, profiles, and absent new artifact refs continue through explicit default/unavailable paths without becoming low-risk, passed, or authoritative.
- [ ] Workflow Kernel canonical version is `0.4.0` and its description/capabilities accurately describe the new neutral mechanics.
- [ ] Assembly canonical version is `3.9.0` and adds hard `workflow-kernel >=0.4.0` dependency.
- [ ] dm-review canonical version is `1.46.0` with `workflow-kernel >=0.4.0` and accurate read-only/fix-loop capability language.
- [ ] Pipeline canonical version is `1.33.0` with `dm-review >=1.46.0`, `workflow-kernel >=0.4.0`, and compatible Assembly optional floor where applicable.
- [ ] Root canonical marketplace versions and every generated Codex manifest agree with canonical plugin manifests.
- [ ] Generated command-skill aliases exactly reflect updated canonical command sources; no generated alias is hand-edited.
- [ ] `tools/check-dependencies.sh` recognizes Assembly, dm-review, and Pipeline as required Kernel consumers at the correct floors.
- [ ] Dual cache resolution remains Claude-first/Codex-fallback and all new runtime lookups fail closed on incompatible, symlinked, or out-of-scope candidates.
- [ ] Documentation describes profile precedence, verification authority, binding invalidation, findings, browser bundles, artifacts, CI, closeout, Scout ordering, compatibility, and human judgment consistently.
- [ ] Plain dm-review remains read-only; fix/loop remain the only approved mutation owners after generated alias regeneration.
- [ ] Improvement Scout output remains proposal-only, accepts empty reports, and cannot gain routing, issue, release, merge, or workflow authority through CLI exposure.
- [ ] Blueprint remains explicitly unresolved without mapping fixtures; no release text claims native authoritative support.
- [ ] Focused new unit suites from Chunks 01–07 pass together under Python 3.12 with the Kernel references on `PYTHONPATH`.
- [ ] `./tools/validate-workflow-kernel.py` passes for Depot-owned checks, or any live sibling-only declaration failure is separately identified with exact safe evidence and does not conceal a Depot regression.
- [ ] `./tools/validate-workflow-contracts.sh` passes, including deterministic read-only review, planner consumption, browser recovery, staging allowlist, CI/closeout, and two-stage Scout ordering checks.
- [ ] `./tools/generate-codex-manifests.py --check` and `./tools/generate-codex-command-skills.py --check` pass after write-mode regeneration.
- [ ] `./tools/check-dependencies.sh`, `./tools/validate-dual-compat.sh`, and `./tools/validate-composition.sh --all` pass, with external/live failures separately classified rather than hidden.
- [ ] `git diff --check` passes and the final diff contains no release publication, tag, installed-cache update, marketplace refresh, merge, or unrelated root work.
- [ ] The chunk receipt lists every generated changed path, exact commands run, pass/fail/unavailable boundaries, current branch/HEAD, and any residual migration risk.
- [ ] Generator output changes exactly the generated paths declared in this prompt and `manifest.json`; any additional generated path blocks staging and returns through the Ambiguity Protocol for a reviewed replan.
- [ ] The branch remains `codex/depot-mechanical-workflow-hardening`, stacked on `origin/codex/adaptive-fusion-verification`, with `noMergeOnCompletion: true` preserved for Pipeline delivery.
- [ ] The implementation leaves sufficient structured evidence for Pipeline Phase 7 to produce the 15-item final requirements crosscheck and exact fresh independent dm-review prompt.

## Required Verification Order

Run focused checks first so failures remain attributable:

1. New Chunk 01 repository verification and evidence binding tests.
2. New Chunk 02 artifact safety tests.
3. New Chunk 03 browser scenario/bundle tests plus existing browser/profile tests.
4. New Chunk 04 review-record tests plus dm-review adapter/events tests.
5. New Chunk 05 CI/closeout tests.
6. New Chunk 06 Assembly profile tests.
7. New Chunk 07 improvements and adapter/parity/metrics tests.
8. CLI, runtime CLI, schema, compatibility, and release-validator suites.
9. Canonical generators in write mode.
10. Kernel release validator.
11. Workflow contract validator.
12. Generator `--check` commands.
13. Dependency and dual-compatibility validators.
14. Full composition validator.
15. `git diff --check` and final status/diff inventory.

If a focused test fails, fix the owning contract before continuing. Do not run
formatters or bulk rewrites over unrelated files. Do not convert an unavailable
live/sibling integration into a pass. Record the exact safe boundary.

## Baseline and Migration Notes

The feature branch started exactly at PR #12 head
`8faeb6ddf00979451c8fd25d7f0bd97f37ae86a8`. The assessment observed
`validate-workflow-contracts.sh` passing and a Kernel validator failure in a live
sibling Assembly declaration path with only a redacted digest. Before judging
new failures, establish whether the exact failing assertion is Depot-owned or
external. New Depot failures are blockers; a proven external declaration remains
visible and unresolved rather than being relabeled green.

The migration strategy is additive:

- new schemas start at version 1;
- existing schemas and `RunSpec` remain closed unless evidence proves a required
  backward-compatible change;
- legacy missing refs get explicit unavailable/default provenance;
- prose remains authoritative during initial shadow comparison;
- promotion to enforcement requires parity evidence outside this chunk's judgment;
- generated Markdown remains a view of structured authority;
- no installed plugin cache changes occur in this run.

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

- Only modify the files and generated surfaces listed above.
- Canonical Claude sources are edited by hand; generated Codex manifests and aliases are changed only by sanctioned generators.
- Do not tag, publish, refresh marketplaces, update installed caches, merge, mark the PR ready, or mutate unrelated root work.
- Keep Workflow Kernel Python 3.12 standard-library-only.
- Do not add provider SDKs, network collection, shell command strings, `shell=True`, or credential/environment inputs to neutral CLI commands.
- Do not weaken exact Docker ownership, cleanup guards, browser recovery, security routing, zero-deferral, final review, or no-merge behavior.
- Do not broaden `RunSpec`, workflow classes, or safety stages solely to store artifact details; prefer immutable references in receipts.
- Do not claim token, cost, time, quality, or Docker savings without direct measured before/after evidence.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

The prior adaptive-verification release demonstrated why exact inventory and
cross-runtime regeneration matter: marketplace source, installed cache, and
launcher behavior can diverge. It also recorded a live sibling Assembly boundary
that should not be confused with a Depot regression. Current versions are Kernel
0.3.0, Assembly 3.8.0, dm-review 1.45.0, and Pipeline 1.32.0. This chunk prepares
the coordinated next minors without publishing them.
