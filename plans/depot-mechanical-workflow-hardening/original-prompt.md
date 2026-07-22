# Original Prompt

## User Request
I had assembly-baseplate make an additional set of recommendations after the recent polishing and testing run and had it write me this prompt. You should evaluate it and make adjustments if warrented, but let's doa. pipline run these too:

## Supplied Pipeline Prompt
Run this work through the full `/pipeline` workflow. Preserve this prompt as `original-prompt.md`, honor all gates, and keep the resulting PR in draft for a fresh independent `dm-review`. Do not merge or publish plugin releases.

# Depot Plugin Hardening: Move Mechanical Agent Work Into Code

Harden the Assembly, Pipeline, Workflow Kernel, and dm-review plugins based on recent Assembly Baseplate execution evidence.

The governing principle is:

> Code establishes facts; agents interpret facts.

Move deterministic orchestration, test selection, evidence binding, browser setup, artifact safety, and closeout reconciliation into executable code. Retain agent judgment for architecture, security threat modeling, UX quality, visual quality, and ambiguous acceptance criteria.

Do not weaken or remove race, security, browser, accessibility, issue-reconciliation, or final-review gates. Expensive verification may move later or to Blueprint, but it must remain explicit and authoritative.

## Baseline gate

Before editing:

1. Read all Depot instructions and current plugin contracts.
2. Refresh `origin/main`, inspect the current branch, worktree status, active PRs, and recent changes.
3. Preserve all existing user work and untracked files. A previously observed checkout had an untracked `.workflow-kernel/` directory; revalidate rather than assuming it is disposable.
4. If the current branch contains unrelated provider-routing work, stop and ask whether to:
   - extend that branch, or
   - create a fresh worktree and `codex/` feature branch.
5. Treat the following as observed leads, not unquestioned truth:
   - `plugins/assembly/agents/workflow/go-test-runner.md` unconditionally runs a full race suite for every Go change and lacks project build-tag awareness.
   - `plugins/assembly/commands/assembly-build.md` contains stale hardcoded build commands such as `./cmd/api`, assumes `docker compose exec`, and omits project-specific test tags.
   - `plugins/dm-review/skills/review/SKILL.md` currently contains a simplification phase that edits and commits code during review.
   - Workflow Kernel already has substantial persona, viewport, route-binding, browser-evidence, recovery, resource, and receipt machinery. Extend it rather than creating a competing system.

## Scope 1: Executable project verification planner

Replace prompt-authored Assembly build/test command selection with a deterministic, project-configurable verification planner.

Create an explicit schema and executable interface that can produce and run a verification plan from repository configuration and the current diff.

It must support:

- repository doctor/preflight;
- generated-code checks;
- focused changed-package tests;
- full non-race tests;
- full race tests;
- CSS/JS/build checks;
- migration validation;
- specialized harness/browser verification;
- remote-only or Blueprint-owned lanes.

Requirements:

- Never hardcode `./cmd/api` or another repository-specific main package in the generic plugin.
- Support repository-declared required build tags such as `-tags=dev`.
- Use Docker exclusively when the repository declares Docker-only Go.
- Select `docker compose exec` only when the intended running service is appropriate.
- Support declared ephemeral `docker compose run --rm --no-deps` execution for worktrees and CI-like tests.
- Prefer command argument arrays or another injection-safe representation over shell strings.
- Parse `go test -json` or equivalent structured output in code.
- Record package results, duration, failures, coverage when requested, command identity, and exit status.
- Never claim a coverage regression without an actual comparable baseline.
- Never run the full race suite merely because any `.go` file changed.

Update Assembly command and agent documentation to consume this executable planner rather than restating commands.

Keep generated Claude/Codex aliases synchronized from their canonical source.

## Scope 2: Tiered testing policy

Encode the following default verification ladder, while allowing repositories to strengthen it:

1. Repository doctor:
   - worktree and branch state;
   - command/profile validity;
   - generated-file drift;
   - `git diff --check`;
   - required tools and runtime availability.
2. Fast deterministic checks:
   - generation;
   - static validation;
   - CSS/JS builds;
   - migrations;
   - documentation links;
   - artifact/secret checks.
3. Focused tests:
   - changed packages and declared dependents;
   - no test cache;
   - required project build tags.
4. Full non-race suite.
5. Risk-selected harness and browser scenarios.
6. Fresh read-only dm-review bound to the exact tested SHA.
7. Merge-candidate remote lanes:
   - full race;
   - security;
   - container scan;
   - other repository-required checks.
8. Post-merge authoritative proof on the main branch.

Race testing is moved, not removed. The planner must report whether each lane is local, Blueprint, GitHub, another provider, or unresolved.

## Scope 3: Make dm-review strictly read-only

Sharpen the command boundaries:

- `dm-review` and `review` inspect and report only.
- `dm-review-fix` applies an explicitly approved finding set.
- `dm-review-loop` owns review → fix → verify iteration.
- A fresh review must not simplify, edit, stage, commit, create issues, change a PR body, mark a PR ready, or merge.
- Move the current automatic simplification/commit behavior out of read-only review and into the appropriate fix workflow.

Bind every review to:

- exact Git SHA;
- tracked dirty-state digest;
- untracked-state classification;
- changed-file inventory;
- build or artifact digest when available;
- verification-profile digest.

If HEAD or the reviewed diff changes, the review must become stale and require a new run.

## Scope 4: Structured incremental reviewer output

Replace Markdown-only inter-agent parsing with a versioned finding schema and incremental JSONL or equivalent durable output.

Each finding must include:

- finding ID;
- rule/category ID;
- severity;
- file and stable line/anchor;
- observed evidence;
- proposed fix;
- source reviewer/provider;
- confidence or disposition where appropriate.

Each reviewer lane must also emit structured:

- files/checks covered;
- `not_covered`;
- commands run;
- provider requested, attempted, and actually used;
- fallback reason;
- completion, partial, unavailable, or failed status.

Persist complete finding records as they are produced. If a reviewer times out or exhausts its budget, already-produced findings must survive.

Consolidation may mechanically normalize, sort, and deduplicate exact or rule-identical findings. Semantic deduplication and severity disputes may still use reviewer judgment.

## Scope 5: Capture browser evidence once

The current dm-review registry invokes multiple browser-oriented reviewers with overlapping runtime work. Separate evidence capture from evidence interpretation.

Extend the existing Workflow Kernel verification model with an executable browser-scenario contract supporting:

- isolated named profiles or cookie jars;
- declared persona and environment fixture references;
- expected login success or lifecycle rejection;
- navigation, input, selection, click, and submission actions;
- JavaScript-disabled execution;
- desktop and mobile viewports;
- focus assertions after morphs or dialogs;
- URL, status, toast, validation, console, and overflow assertions;
- application restart followed by session-state verification;
- screenshot, trace, and console evidence;
- explicit `human_action_required` steps for MFA, passkeys, QR scans, or external sign-in.

Do not persist raw passwords, cookies, tokens, QR secrets, or private origins in receipts.

Capture one immutable runtime evidence bundle. Allow visual-browser, UX-quality, UI-standards, accessibility, and other reviewers to inspect that shared bundle independently instead of each repeating setup, login, navigation, and screenshots.

The kernel must continue to distinguish browser proof from curl/reachability proof.

## Scope 6: Evidence-to-build binding

Every verification receipt must identify what was actually tested.

Add safe bindings for:

- commit SHA;
- tracked dirty-state digest;
- untracked-state classification/digest;
- compiled binary or container-image digest when available;
- harness configuration/profile digest;
- scenario/verification-profile digest;
- command identity;
- start and finish timestamps;
- exit status;
- evidence references.

A receipt from an earlier binary, branch, or dirty state must not satisfy a later exact-head gate.

Generate human-readable Markdown reports from structured state. Do not maintain a second manually editable status source that can contradict the structured evidence.

## Scope 7: Artifact privacy and staging safety

Structured receipt redaction is not sufficient because screenshots, traces, console logs, and untracked files can contain real personal information or credentials.

Add an artifact classifier with at least:

- `committable`;
- `private_receipt`;
- `ephemeral`;
- `blocked_sensitive`.

Inspect text artifacts, traces, console output, filenames, and other feasible metadata for:

- real email addresses;
- cookies and authorization headers;
- tokens and passwords;
- MFA/QR/authenticator material;
- private URLs and environment values.

Allow explicitly declared fictional `.test` and `.example` fixture identities.

Generate an explicit staging allowlist from intended changed files and classified artifacts. Never rely on broad `git add .` during closeout.

## Scope 8: Provider-neutral CI evidence

Add a normalized CI/check model:

- provider;
- workflow/run/job identity;
- scope: pull request, push, scheduled, or post-merge;
- lane: test, race, security, container scan, deployment, or project-defined;
- status: queued, running, passed, failed, skipped, cancelled, or unavailable;
- authoritative boolean;
- evidence URL/reference.

Support GitHub and Blueprint without treating one provider’s skipped jobs as success merely because another provider may be configured.

Merge readiness must require authoritative evidence from the configured provider. PR-lane success must not be presented as post-merge or scheduled-lane proof.

## Scope 9: Deterministic PR and issue closeout

Implement a code-driven closeout audit that can verify:

- local HEAD equals remote PR head;
- reviewed SHA equals remote PR head;
- expected draft/ready state;
- required verification gates;
- PR body issue references;
- actual issue state;
- referenced receipts and screenshots exist;
- changed files match claimed scope;
- remaining open issues on the affected surface are reported.

Support at least these dispositions:

- `Fixes/Closes` only when all declared closure evidence passes;
- non-closing `Refs` for implemented but incomplete work;
- blocked closure with explicit missing evidence.

Natural-language acceptance criteria still require human or reviewer judgment to map them to evidence requirements. Once mapped, code must prevent contradictory closing claims.

Verify that GitHub parsed the final references.

## Scope 10: Pipeline integration

Update Pipeline to consume the new structured mechanics:

- verification-plan output;
- test receipts;
- reviewer finding ledgers;
- browser evidence;
- CI evidence;
- issue-closeout evidence;
- exact-head bindings.

Keep semantic planning, scope approval, architectural decisions, and merge recommendations in their existing human/agent authority.

Use the Workflow Kernel’s shadow/parity mechanism for new deterministic behavior before promoting enforcement. Do not give the kernel authority to invent requirements, waive findings, or approve merges.

Avoid duplicating schemas and contracts across Assembly, Pipeline, dm-review, and Workflow Kernel. Workflow Kernel should own neutral mechanics; Assembly should own Assembly-specific defaults; Pipeline and dm-review should consume them.

## Verification

Add comprehensive tests for:

- repository profile parsing and rejection;
- safe Docker command selection;
- required build tags;
- changed-package selection;
- race-lane deferral without omission;
- stale command/path rejection;
- review read-only enforcement;
- review invalidation after HEAD changes;
- incremental partial reviewer output;
- browser scenario validation and human-action pauses;
- evidence/build binding mismatch;
- artifact sensitivity classification;
- explicit staging allowlists;
- GitHub and Blueprint skipped/passed semantics;
- PR closing versus reference dispositions;
- malformed, symlinked, oversized, or hostile inputs;
- stable CLI JSON and exit codes;
- Claude/Codex generated-command parity.

Run Depot’s canonical workflow-contract validation, focused Workflow Kernel tests, full relevant plugin tests, generator checks, and `git diff --check`.

Measure and report before/after:

- number of agent lanes;
- repeated browser setup operations;
- deterministic versus agent-owned actions;
- local fast/focused/full/race durations where practical;
- active compute versus human/external/capacity/CI waits;
- any remaining manual steps.

Do not invent savings when telemetry is unavailable.

## Delivery

- Use small cohesive commits.
- Keep unrelated current work intact.
- Update plugin documentation and schemas with the code.
- Record migration/compatibility behavior for existing consumers.
- Produce a final requirements crosscheck with direct code/test evidence.
- Open or update a draft PR.
- Include accurate closing or non-closing issue references.
- Leave the PR draft for a fresh independent `dm-review`.
- Do not merge, tag, publish, refresh marketplaces, or update installed plugin caches in this run.

The final handoff must state:

- exact branch and commit;
- what mechanical work moved from agents into code;
- what remains intentionally agent-owned;
- tests and contract validators run;
- browser/runtime proof completed or still required;
- CI/provider boundary;
- migration risks;
- open findings and issue dispositions;
- the exact prompt for the fresh dm-review session.

## Date
2026-07-22

## Key Requirements Extracted
1. Preserve current work, use the approved isolated branch stacked on PR #12, and keep delivery as an unmerged draft PR without publishing releases or caches.
2. Add a deterministic, project-configurable verification planner with safe argument arrays, repository profiles, structured results, and no generic hardcoded application paths.
3. Encode an explicit tiered verification ladder that preserves race, security, browser, accessibility, remote, and post-merge authority while selecting local work by risk and changed scope.
4. Make `dm-review` and `review` strictly read-only; reserve mutation for explicitly approved `dm-review-fix` and `dm-review-loop` flows.
5. Bind reviews and verification to exact Git/build/profile state and invalidate stale evidence after relevant state changes.
6. Persist versioned structured reviewer findings incrementally, preserving partial results, provenance, coverage gaps, provider routing, and stable identity.
7. Extend Workflow Kernel's existing browser verification and recovery model into executable scenarios and a single immutable evidence bundle shared by independent reviewers.
8. Classify artifacts by sensitivity and lifecycle, redact private evidence safely, and generate explicit staging allowlists rather than relying on broad staging.
9. Normalize provider-neutral CI evidence without confusing PR, push, scheduled, skipped, and post-merge authority across GitHub, Blueprint, or other providers.
10. Add deterministic PR and issue closeout auditing for exact heads, draft/ready state, required evidence, issue references/state, claimed scope, and closing versus non-closing dispositions.
11. Keep neutral mechanics in Workflow Kernel, Assembly-specific defaults in Assembly, and Pipeline/dm-review as consumers; use shadow/parity before enforcement and preserve human judgment boundaries.
12. Add comprehensive hostile-input, schema, CLI, contract, generator-parity, and integration tests and run Depot's canonical validators.
13. Measure only available before/after evidence for agent lanes, repeated setup, deterministic ownership, durations, waits, and manual steps; never invent savings.
14. Produce a final evidence-backed requirements crosscheck and an exact fresh independent dm-review prompt while leaving the resulting PR draft.
15. Add an every-run, proposal-only Upstream Improvement Scout that emits structured candidates and a generated reusable upstream Pipeline prompt, including a valid empty result when no evidence-backed improvement exists.

## Iteration 1 Feedback

What do you think about adding in a step to the pipeline that helps with plugin improvement? It would be nice if after each run, it could share new places that could use coded checks/lints/etc, or places to change or improve existing ones, and also highlight other potential areas for depot improvement. The result would be a prompt I pass back to you for upstream changes.

### Requirement Interpretation

- Add an every-run, proposal-only upstream improvement pass after execution, verification, final review, and cleanup evidence are available, but before final delivery.
- Mine direct run evidence for opportunities to move repeated mechanical work into deterministic code, checks, lints, validators, schemas, or tests; improve existing checks; strengthen plugin contracts; close telemetry gaps; and improve Depot architecture or documentation.
- Keep this pass distinct from the friction-triggered Codify loop and the run-economics postmortem. It must run even when the feature run is clean.
- Emit both structured candidate data and a generated, ready-to-run upstream implementation prompt that can be passed into a separate fresh Pipeline run.
- Make the pass observation- and proposal-only. It must not modify plugin sources, routing policy, workflow requirements, review findings, merge authority, releases, marketplaces, or installed caches.
- Require every candidate to cite direct evidence from run receipts or artifacts, distinguish one-off observations from recurring patterns, deduplicate against existing checks and known recommendations, state target plugin/files and acceptance criteria, and avoid invented time, token, cost, or quality savings.
- Emit a valid empty result when no evidence-backed improvement exists rather than manufacturing upstream work.

## Iteration 2 Feedback

The user explicitly approved `workflowClass: feature` for the new plan.
