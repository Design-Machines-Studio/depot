# Chunk: Assembly Repository Profile

## Context

This is Chunk 06 of Depot Mechanical Workflow Hardening. The live Assembly
Baseplate repository uses project-specific Docker, Go-tag, package, CI, and UX
contracts that the current Assembly plugin misstates. Chunks 01 and 03 provide
the neutral repository planner and browser scenario model. This chunk supplies
Assembly-owned defaults and makes the public Assembly build/test guidance consume
those mechanics.

## Task

Add a Baseplate repository verification profile under the canonical Assembly
build skill and replace stale hardcoded command selection in Assembly sources.
Keep the profile project-configurable and conservative when a consuming project
does not match or supplies incomplete declarations.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/assembly/skills/assembly-build/references/assembly-baseplate-verification-profile.json` | Create | Assembly-owned default profile consumed by Kernel planner |
| `plugins/assembly/skills/assembly-build/references/assembly_verification_adapter.py` | Create | Approved review-remediation adapter that mechanically resolves profile, repository/runtime proof, planning, and UX declarations |
| `plugins/assembly/agents/workflow/go-test-runner.md` | Modify | Select focused/full/race work through planner results |
| `plugins/assembly/commands/assembly-build.md` | Modify | Canonical standalone command invokes planner and safe argv results |
| `plugins/assembly/skills/development/setup.md` | Modify | Remove stale exec/app/api/untagged assumptions |
| `tests/test_assembly_verification_profile.py` | Create | Profile fixture, project override, UX declaration, conservative fallback |

Do not edit `plugins/assembly/skills/assembly-build/SKILL.md` because it is a
generated command-skill alias. Do not edit Assembly or other plugin manifests,
versions, root marketplace data, Kernel CLI, Pipeline orchestration, or generated
Codex manifests. Chunk 08 owns generation and dependency metadata.

### Approved Scope Amendment

The Phase 6 hostile review proved that repository/runtime/UX safety expressed
only through Markdown and test-local helpers could not enforce the public
Assembly workflow. The pipeline owner approved the narrow production adapter
listed above as a zero-deferral remediation. This amendment does not authorize
changes outside the Assembly build references, the original documentation, and
the original focused test file; release and generated surfaces remain Chunk 08.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/assembly/commands/assembly-build.md` | Canonical source for generated alias |
| `plugins/assembly/agents/workflow/go-test-runner.md` | Current full-race-for-any-Go policy |
| `plugins/assembly/skills/development/setup.md` | Repeated stale command assumptions |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/repository_verification.py` | Chunk 01 profile/plan API |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-profile-schema.json` | Required profile shape |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_scenario.py` | Chunk 03 scenario declaration mapping |
| `/Users/trav/Websites/design-machines/assembly-baseplate/Makefile` | Live canonical Docker/build/test targets |
| `/Users/trav/Websites/design-machines/assembly-baseplate/.github/workflows/test.yml` | Live PR/push/schedule lane authority |
| `/Users/trav/Websites/design-machines/assembly-baseplate/tests/ux/README.md` | Markdown-first persona/task declaration contract |

## Patterns to Follow

The live Baseplate defaults currently include:

```text
GO_DOCKER = docker compose run --rm --no-deps app
templ generate = go tool templ generate
project tests = go test -tags=dev ./...
race tests = go test -tags=dev -race -timeout=60m ./...
application package = ./cmd/assembly
focused permissions = ./internal/auth ./internal/baseplate/admin ./internal/baseplate/members ./internal/testutil
```

These are Assembly profile defaults, not neutral Kernel defaults. The profile
must encode safe argv arrays, never a shell command string. Project-local explicit
config outranks this profile. A nonmatching repository or incomplete explicit
declaration reports unavailable instead of falling back to stale generic paths.
Focused/full test argv used as fresh verification must include the declared
cache-disabling flag (`-count=1`) so a cached package result is not reported as
new execution evidence. Compose `exec` versus ephemeral `run --rm --no-deps`
selection must derive from declared runtime/service state; a stopped, stale, or
unverified service can never trigger `exec` by assumption.

The tier policy must distinguish:

- local schema/static/generator checks;
- changed-package or declared focused tests;
- full project tests;
- race, security, and container scanning;
- UX task validation, browser, and accessibility scenarios;
- PR, push, schedule, merge-group, and post-merge evidence.

Baseplate's current GitHub Test workflow runs full tests on ready PRs while
`test-race` and `container-scan` are non-PR lanes. The profile must preserve this
scope rather than presenting skipped PR jobs as repository-wide proof.

For `tests/ux/`, task frontmatter is authoritative. Discover declared runnable
statuses, persona IDs, routes, required authentication, expected outcomes,
viewports, engines when declared, and screenshot points. Missing declarations
may be `not_declared`; present-but-invalid declarations are blocking.

## Companion Skills

Load `assembly:development` for Assembly Docker/Templ/Datastar conventions and
`assembly:assembly-build` for the current public build surface. Source files in
this branch override installed-cache copies.

## Acceptance Criteria

- [ ] The Baseplate profile validates against Chunk 01's strict schema and contains only safe argument arrays, stable lane IDs, explicit tiers, authority, selectors, and provenance.
- [ ] Default isolated Go execution uses Compose `run --rm --no-deps app`, includes `-tags=dev`, and builds/tests `./cmd/assembly` rather than `./cmd/api`.
- [ ] Focused/full Go test argv explicitly includes `-count=1` for fresh evidence while preserving `-tags=dev`, and tests prove the cache-disabling flag cannot be omitted by profile translation.
- [ ] Compose `exec` is selected only when declared runtime/service-state evidence proves the intended service is running and appropriate; absent, stopped, stale, or mismatched state selects declared ephemeral `run --rm --no-deps` or returns unavailable.
- [ ] Focused package selection is derived from changed scope or explicit project declarations; any Go change no longer automatically forces full race locally.
- [ ] Full, race, security, container, browser, accessibility, PR, push, schedule, merge-group, and post-merge lanes remain available and cannot be satisfied by a lower tier.
- [ ] PR-lane results never stand in for the Baseplate non-PR `test-race` or `container-scan` lanes.
- [ ] Project-local explicit configuration outranks the plugin profile; profile defaults outrank heuristics; unmatched/incomplete inputs return explicit unavailable/blocking state.
- [ ] UX task discovery reads task status/persona/route/auth/expected outcome/viewport/screenshot declarations and does not treat a generated coverage matrix as authority.
- [ ] Browser criteria preserve failed evidence, primary quit, fresh-primary retry, different-engine attempt, then `human_help_required`; curl remains diagnostic only.
- [ ] `go-test-runner.md`, `assembly-build.md`, and `setup.md` describe the same profile/planner path without duplicated hardcoded application assumptions.
- [ ] Standalone `/assembly-build` fails with actionable unavailable evidence when Workflow Kernel or a valid profile cannot be resolved; it does not silently run guessed commands.
- [ ] Tests include valid Baseplate defaults, project override, changed-package focus, high-risk escalation, cache-disabled focused execution, running/stopped/stale service exec-versus-run selection, PR versus scheduled scope, absent UX declarations, malformed present declarations, and unsupported repository cases.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_assembly_verification_profile`.
- [ ] No generated alias, plugin manifest, version, marketplace, release inventory, or installed cache is modified in this chunk.
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
- Assembly-specific defaults stay in Assembly; never copy them into neutral Kernel defaults.
- Do not use shell command strings, `shell=True`, bare host Go commands, or environment values in the profile.
- Do not modify the sibling Assembly Baseplate repository; it is read-only evidence for this Depot chunk.
- Do not run a live browser and do not claim browser verification from contract tests.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

The Baseplate Makefile and CI workflow are live evidence that the current plugin
guidance is stale. Baseplate also includes markdown-first persona tests with
status-aware runnable coverage. Moving these declarations into a profile lets
the Kernel choose mechanical work while agents continue to interpret risk and UX.
