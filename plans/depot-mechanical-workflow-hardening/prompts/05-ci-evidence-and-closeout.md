# Chunk: CI Evidence and Deterministic Closeout

## Context

This is Chunk 05 of Depot Mechanical Workflow Hardening. Depot currently has no
provider-neutral CI model, while PR/issue reconciliation is a strong but
agent-executed prose contract. Chunk 01 supplies exact repository/evidence
identity. This chunk makes CI and closeout facts deterministic without giving
Workflow Kernel network access or merge authority.

GitHub provider state and repository policy must remain separate. A raw skipped
or neutral conclusion can satisfy some GitHub rules without becoming a passed
test. PR, push, schedule, merge-group, and post-merge evidence are distinct.
Blueprint semantics remain unresolved until an explicit adapter mapping exists.

## Task

Implement strict provider-neutral CI evidence records, a separate CI gate
decision, and a pure PR/issue closeout evaluator. Provider collection remains in
adapters or callers. Core code accepts normalized snapshots and validates their
authority against declared repository requirements.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/ci_evidence.py` | Create | Scope, lane, raw provider state, requirements, gate decision |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/closeout.py` | Create | Pure PR/issue/scope/evidence reconciliation evaluator |
| `plugins/workflow-kernel/skills/workflow-kernel/references/ci-evidence-schema.json` | Create | Strict version-1 provider-neutral CI snapshot |
| `plugins/workflow-kernel/skills/workflow-kernel/references/closeout-audit-schema.json` | Create | Strict version-1 expected/observed audit result |
| `tests/test_ci_evidence.py` | Create | GitHub-like and opaque Blueprint fixtures, scope/authority cases |
| `tests/test_closeout.py` | Create | Exact head/draft/reference/scope/evidence cases |
| `plugins/dm-review/skills/review/references/issue-tracking.md` | Modify | Align prose with parsed/provider-resolved/actual disposition facts |

Do not add GitHub SDKs, HTTP calls, `gh` invocation, Blueprint assumptions, CLI
registration, adapter stages, Pipeline orchestration, plugin versions, manifests,
or generated files. Chunks 07 and 08 own integration and release wiring.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/evidence_binding.py` | Exact SHA/build/evidence identity from Chunk 01 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/git.py` | Existing local exact Git proof |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/redaction.py` | Safe provider/raw reference handling |
| `plugins/dm-review/skills/review/references/issue-tracking.md` | Existing eight-part closure reconciliation |
| `tests/test_pipeline_adapter.py` | Provider receipt and event-scope test style |
| `tests/test_git_cleanup.py` | Exact Git identity and fail-closed handling |

## Patterns to Follow

- Core modules are pure and provider-neutral; callers/adapters collect network
  state and pass explicit snapshots.
- Strict records preserve provider-native status/conclusion strings and opaque
  redacted metadata alongside normalized fields.
- Authority is derived from a declared required-check/lane policy containing
  provider, context/lane, event scope, subject kind, and expected app/integration.
- Unknown provider mapping, unavailable repository policy, missing subject SHA,
  or stale observation yields `unresolved`/`unavailable`, never success.
- Use stable run/job/check IDs and safe URLs/references, not scraped labels.

The CI evidence model must represent:

- provider and adapter/mapping version;
- event scope such as pull request, push, schedule, merge group, post merge;
- ref, base SHA, PR head SHA, test-merge SHA, subject SHA and subject kind;
- run/check/job ID, attempt, check kind, context/name, app/integration identity;
- raw status and raw conclusion;
- normalized lifecycle and conclusion without losing raw values;
- timestamps, URL/evidence reference, required-policy provenance, and observation time;
- a separately derived `satisfies_provider_merge_rule` or neutral equivalent.

GitHub-oriented fixtures must prove:

- only completed checks have conclusions;
- success, skipped, and neutral remain distinct even when policy accepts them;
- cancelled, timed-out, stale, action-required, and failure remain non-success;
- whole-workflow filter skips can leave a required check pending;
- conditional job skips can report success;
- test-merge evidence and PR head evidence are not interchangeable;
- expected GitHub App/integration identity can be part of authority;
- strict versus loose up-to-date policy is represented.

Blueprint fixtures are project-declared adapter examples only. Keep the raw
status opaque and require an explicit mapping table/capability declaration. If
mapping or authoritative subject identity is absent, return unresolved.

The closeout evaluator must compare expected and observed:

- local HEAD, reviewed SHA, delivered SHA, PR head SHA, and base/default branch;
- expected versus actual draft state;
- required CI/evidence records and their exact subject bindings;
- changed-file scope versus claimed scope;
- textual references, parsed mention/closing intent, provider-resolved entity,
  provider closing link, actual issue state, and repository auto-close policy;
- referenced receipt/screenshot artifact path, expected digest, observed
  existence/digest/classification, and binding validity;
- a provider-supplied affected-surface open-issue inventory with scope/mapping
  provenance, distinct from findings and from issues merely mentioned by the PR;
- remaining unresolved findings/surfaces/open issues and final
  closing/non-closing disposition.

Do not use `merge_commit_sha` as the PR head. A PR body closing keyword only
creates provider closing linkage against the default branch, and repository
auto-close can be disabled. Plain mentions do not imply closure.

## Companion Skills

No companion skill is required. Use official semantics preserved in the research
brief and local strict-schema patterns. Do not browse or invent new provider APIs.

## Acceptance Criteria

- [ ] CI and closeout schemas are strict, bounded, versioned, secret-safe, and deterministic.
- [ ] CI records retain raw provider status/conclusion and compute normalized lifecycle/conclusion separately.
- [ ] `success`, `skipped`, and `neutral` remain distinct even when a declared GitHub policy accepts all three.
- [ ] Authority binds provider, event scope, subject kind/SHA/ref, check kind/context, expected app/integration, requirement source, run/job IDs, attempt, and observation time.
- [ ] PR, push, schedule, merge-group, default-branch, and post-merge evidence cannot satisfy one another by shared labels alone.
- [ ] Missing/stale SHA, unknown required policy, unmapped raw state, wrong app source, absent lane, or unavailable provider returns unresolved/unavailable rather than passed.
- [ ] Blueprint fixtures require explicit adapter mapping and capability flags; GitHub semantics are never assumed.
- [ ] Closeout compares local, reviewed, delivered, and actual PR head identity and rejects synthetic merge SHA substitution.
- [ ] Draft expected/actual state, required evidence, claimed versus changed-file scope, and unresolved findings appear as separate audit checks.
- [ ] Every referenced receipt and screenshot is checked as a separate pure snapshot fact for existence, expected digest, safe classification, and current binding; missing, tampered, private-only, or stale artifacts have distinct reason codes and cannot satisfy closure evidence.
- [ ] A provider-collected affected-surface open-issue inventory is an explicit bounded input with scope and mapping provenance; remaining open issues are reported separately from PR references and unresolved review findings, while unavailable inventory remains unresolved.
- [ ] Parsed mention, closing intent, provider-resolved issue, provider closing link, and actual issue closure are separate fields/dispositions.
- [ ] Non-default-base closing keywords and disabled/unknown auto-close policy do not become guaranteed closure.
- [ ] Provider collection/network actions are absent from core evaluation; audit execution is pure and non-mutating.
- [ ] `issue-tracking.md` uses the structured distinctions without weakening zero-deferral or authorizing plain review to mutate issues.
- [ ] Tests cover GitHub raw conclusions, filtered versus conditional skips, strict policy, wrong app, test-merge/head, scheduled gaps, Blueprint unresolved, transferred/missing/non-issue references, draft mismatch, scope mismatch, missing/tampered/stale receipt and screenshot references, unavailable and populated affected-surface open-issue inventories, and exact clean closeout.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_ci_evidence tests.test_closeout tests.test_git_cleanup`.
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
- Keep core evaluation pure, standard-library-only, observation-only, and non-mutating.
- Do not add network calls, SDKs, `gh`, shell execution, credentials, or provider secrets.
- Do not equate green-looking, skipped, neutral, or missing checks with authoritative success without current declared policy.
- Do not invent Blueprint statuses, conclusions, scopes, IDs, or merge rules.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Official GitHub documentation confirms that check lifecycle and conclusion are
distinct, required policy can accept skipped/neutral, PR workflows often bind a
test-merge SHA, scheduled runs bind the default branch, and closing keywords only
create closing linkage on the default branch. No authoritative public Blueprint
CI contract or local payload fixture was found, so unresolved is mandatory.
