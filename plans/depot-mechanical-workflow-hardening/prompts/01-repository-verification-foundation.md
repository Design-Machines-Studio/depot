# Chunk: Repository Verification Foundation

## Context

This is Chunk 01 of the Depot Mechanical Workflow Hardening feature.
Workflow Kernel already owns strict behavioral contracts, repository scope,
canonical digests, and cleanup-oriented Git proof. This chunk adds the neutral
foundation that later artifact, browser, review, CI, Assembly, and Pipeline
chunks will consume. It must not implement those consumers yet.

The approved design separates repository policy, a derived per-change plan,
observed lane results, and exact build/evidence identity. Do not create a
universal receipt or overload the browser-persona `VerificationProfile`.

## Task

Implement strict version-1 Workflow Kernel contracts for:

1. shared safe argument-array validation;
2. repository verification profiles;
3. deterministic verification plan derivation;
4. structured verification lane results; and
5. exact Git/build/profile/evidence binding with a pure stale-match gate; and
6. bounded execution of selected local lanes, including repository-doctor
   checks and structured Go test result parsing.

Keep the runtime Python 3.12 standard-library-only. Expose pure module APIs and
schemas in this chunk. Chunk 08 owns shared CLI registration, package exports,
release inventories, manifests, and version bumps.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/argv.py` | Create | One shared safe argv validator extracted from the behavioral contract rules |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/repository_verification.py` | Create | Profile, lane, plan, result, derivation, canonical digest |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_execution.py` | Create | Bound-repository safe-argv execution, doctor checks, structured parser dispatch |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/evidence_binding.py` | Create | Exact source/build/profile/command/evidence binding and match result |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-profile-schema.json` | Create | Strict version-1 profile schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-plan-schema.json` | Create | Strict derived-plan schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-result-schema.json` | Create | Strict observed-result schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/evidence-binding-schema.json` | Create | Strict build/evidence identity schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/behavioral_contract.py` | Modify | Consume the shared argv validator without changing existing behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/repository_scope.py` | Modify if required | Reuse scope identity without widening its cleanup contract |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/git.py` | Modify if required | Factor reusable capture helpers; keep `GitProof` cleanup-specific |
| `tests/test_repository_verification.py` | Create | Profile, planning, lane, precedence, hostile-input tests |
| `tests/test_verification_execution.py` | Create | Doctor, safe execution, Go JSON parsing, coverage-baseline tests |
| `tests/test_evidence_binding.py` | Create | Git/build/dirty/untracked/digest/staleness tests |
| `tests/test_behavioral_contract.py` | Modify | Prove argv extraction has exact behavioral parity |
| `tests/test_repository_scope.py` | Modify if required | Prove scope compatibility after helper reuse |

Do not modify `workflow_kernel/cli.py`, package exports, release validators,
plugin manifests, marketplace files, generated Codex files, or consumer plugin
documents in this chunk.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/behavioral_contract.py` | Existing hostile argv checks and strict contract style |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification.py` | Existing persona/browser profile that must remain separate |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/repository_scope.py` | Canonical repository identity |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/git.py` | Existing cleanup-specific exact Git proof |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/limits.py` | Bounded JSON parsing helpers |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/redaction.py` | Safe durable strings and secret-shape rejection |
| `plugins/workflow-kernel/skills/workflow-kernel/references/behavioral-verification-contract-schema.json` | Strict schema conventions |
| `tests/test_behavioral_contract.py` | Existing negative-case style |

## Patterns to Follow

- Exact objects reject missing and unknown keys; do not silently widen legacy shapes.
- Use frozen dataclasses or immutable tuples for canonical inputs.
- Canonical JSON uses sorted keys and compact separators before SHA-256 identity.
- Durable errors use bounded reason codes and never republish raw secret values.
- Preserve `schema_version: 1` per new independent document.
- Reuse `_OwnedResourceScope`, durable-path binding, redaction, and limits where
  applicable instead of adding filesystem or JSON helpers.

The current behavioral contract rejects shell command-string modes, environment
split-string forms, secret-bearing flags, empty arguments, control characters,
and unbounded arrays. Move this logic behind a public-to-Kernel shared helper,
then prove all existing behavioral-contract tests still pass byte-for-byte.

The repository profile must represent policy, including:

- profile ID/version/source and canonical digest;
- project marker/declaration paths and explicit precedence provenance;
- named lanes with safe argv arrays;
- local, focused, broad, race, security, container, browser, accessibility,
  remote PR, push, schedule, merge-group, and post-merge tiers;
- change/path/package selectors and risk escalators;
- expected authority and whether a lane is locally runnable;
- parser kind, working-directory binding, timeout/output bounds, and declared
  runtime/service prerequisites for each runnable lane;
- deterministic omission reasons and explicit unavailable states;
- no embedded credentials, environment values, or application-specific defaults.

The derived plan must bind:

- repository scope and exact HEAD/tree identity;
- tracked diff digest and classified untracked state;
- profile digest and relevant declaration digests;
- changed paths/packages and declared risk inputs;
- selected lanes and omitted lanes with reason codes;
- expected authority and execution budget;
- plan digest and generation timestamp supplied by the caller.

The lane result must preserve selected lane ID, plan digest, observed status,
exit state, timing, evidence references, and raw unavailable/skipped distinctions.
For a declared `go-test-json` parser it also preserves per-package outcome,
duration, failures, optional coverage, command identity, and parser diagnostics.
It must not infer success from absence.

The execution API must accept only a selected locally-runnable lane from a
validated plan whose repository/profile/command binding still matches. Execute
the lane's argv directly with `subprocess` and `shell=False`, from the bound
repository-relative working directory, with explicit timeout/output limits and
no caller-supplied environment values. It must never accept a free-standing
command or shell string that bypasses the plan/profile authority.

Repository doctor/preflight is an explicit lane/result contract. It checks the
bound branch/worktree state, profile and command validity, declared generator
drift commands, diff-check commands, and required tool/runtime/service
availability. A missing tool, stopped required service, stale profile, unsafe
command, dirty-state mismatch, or unavailable generator is recorded distinctly;
none becomes a passing preflight. Generator and diff checks remain safe argv
declared by the repository profile rather than neutral hardcoded app paths.

Parse newline-delimited `go test -json` events in code with bounded event and
package counts. Preserve package pass/fail/skip, elapsed duration, test/action
failures, optional coverage when requested, command identity, exit status, and
malformed/truncated-stream reason codes. Coverage comparison is permitted only
when the current and baseline records have matching package scope, command,
tags, coverage mode, profile, and comparable binding metadata; otherwise the
comparison is `unavailable`, never a regression claim.

The evidence binding must represent exact commit/tree, dirty tracked digest,
classified untracked digest or explicit exclusions, profile/plan/scenario digest,
safe command identity, optional binary/image digest, started/completed time, exit
state, and evidence digest. Dirty state may be valid but can never be hidden.

## Companion Skills

No companion skill is required. Follow the repository `AGENTS.md`/`CLAUDE.md`
and the existing Workflow Kernel modules listed above.

## Acceptance Criteria

- [ ] Four new strict JSON schemas reject unknown keys, missing keys, wrong types, duplicate identities, excessive collections, invalid timestamps, traversal, and secret-shaped durable values.
- [ ] Safe argv is implemented once and existing behavioral-contract acceptance/rejection behavior remains unchanged, including shell-string and secret-bearing flag cases.
- [ ] Repository profile precedence is explicit: project configuration, then plugin profile, then conservative `unavailable`; heuristic discovery never silently overrides either source.
- [ ] The planner produces byte-deterministic output for the same normalized profile, repository state, change set, risk input, and supplied timestamp.
- [ ] Selected and omitted lanes both appear in the plan with stable IDs, tier, reason, expected authority, and runnable state.
- [ ] Lower-tier evidence cannot satisfy race, security, browser, accessibility, remote, push, schedule, merge-group, or post-merge requirements unless the profile explicitly declares that exact authority.
- [ ] Verification results preserve `passed`, `failed`, `skipped`, `unavailable`, and `blocked` without collapsing them into a boolean.
- [ ] A selected local lane runs only from its still-current validated plan/profile binding, uses its safe argv directly with `shell=False`, stays inside the bound repository working directory, and enforces declared timeout/output limits without accepting caller environment values or free-standing commands.
- [ ] Repository doctor emits separate deterministic checks for branch/worktree binding, profile/command validity, generator drift, diff check, required tools/runtimes, and declared service state; missing, stale, unsafe, stopped, and unavailable conditions never normalize to passed.
- [ ] The bounded `go-test-json` parser records per-package result, duration, failures, optional requested coverage, command identity, exit status, and malformed/truncated-stream reason codes.
- [ ] Coverage comparison reports a regression only with a comparable baseline matching package scope, command, tags, coverage mode, profile, and binding metadata; absent or incomparable baselines are explicit `unavailable`.
- [ ] Build bindings distinguish commit, tree, tracked dirty state, classified untracked state, profile/plan/scenario, command, artifact/image, timing, exit, and evidence identities.
- [ ] A pure binding-match API reports specific mismatch reason codes for HEAD, tracked diff, untracked classification, profile, plan, scenario, command, artifact/image, and evidence changes.
- [ ] Existing `RepositoryScope`, cleanup `GitProof`, behavioral contracts, and persona/browser `VerificationProfile` retain their public semantics and focused tests pass.
- [ ] No generic `docker compose exec app`, `./cmd/api`, Go build tag, package, browser, or route assumption is embedded in neutral Kernel defaults.
- [ ] New code imports only Python 3.12 standard-library modules and existing Kernel modules.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_repository_verification tests.test_verification_execution tests.test_evidence_binding tests.test_behavioral_contract tests.test_repository_scope`.
- [ ] `git diff --check` passes and no file outside the declared chunk scope changed.

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
- Follow existing patterns; do not add runtime dependencies or a second harness.
- Do not modify `RunSpec`, workflow stages, failure enums, CLI registration, manifests, versions, generated Codex artifacts, or consumer plugins in this chunk.
- Do not reinterpret absent legacy fields as low risk, passed, or authoritative.
- Do not add shell execution, `shell=True`, command strings, or environment-value persistence.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

PR #12 already supplies content-addressed behavioral contracts, repository
scope, stable review identity, browser recovery, cleanup ownership, and attempt
economics. Research found no repository-aware planner or reusable build binding.
Assembly Baseplate proves why generic inference is unsafe: its live commands use
Docker Compose `run --rm --no-deps app`, `-tags=dev`, and `./cmd/assembly`, while
its higher-authority race/security/container and CI lanes vary by event scope.
