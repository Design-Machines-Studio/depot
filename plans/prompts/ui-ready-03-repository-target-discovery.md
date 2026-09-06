# UI-READY-03: discover documented repository browser targets

Work in `Design-Machines-Studio/depot` from `/home/ned/ai/depot`.
Exact planning base: `76267e0e10845e1f9ea4a5eb533b6ca9628b12be`.

executorRole: builder-deep
executorCapabilities: [read-repository, write-repository, tool-use, long-context, structured-output]
executorEffort: high

Resolve these fields through the installed model-router. Participant packets
must contain no concrete model, provider, rail, candidate ordering, or prices.
Browser interaction belongs to the host; do not request a routed browser
capability. Use direct bounded implementation, not a full Pipeline.

## Workspace and authority

Read AGENTS.md, its referenced instructions, CLAUDE.md, the current planning
index, and applicable plugin contracts. Refresh authenticated GitHub state and
origin/main. If main advanced, inspect the intervening diff and record the new
exact base before proceeding; stop only for a material scope/ownership conflict.

Preserve the primary checkout and every existing worktree. At planning time the
primary was `bench/gpt-6-astra-screen` at
`6ab616fd5e3bd5c7f2e11ed44677413f0d8de759`, with a modified CLAUDE.md,
169 deleted tracked todos, and an untracked nested benchmark checkout. Do not
stash, reset, clean, switch, rebase, discard files, or remove existing worktrees.
Create a clean worktree outside it, under `/home/ned/ai/depot-worktrees/`, on a
new `fix/ui-ready-03-repository-target-discovery` branch from refreshed main.
The separate `docs/depot-planning-20260907` worktree owns coordination only;
do not absorb it or edit its files. Check for a newer owner/PR before starting.

## Demonstrated problem and owner

Owner: dm-review. Current version 1.79.1 only accepts an invocation URL,
attached automation-capable T3 preview, `.dm/ui-review.json`, or accepted exact
Pipeline browser evidence. Its required prepare path exits 76 with
`visual_target_unavailable` before inspecting ordinary repository instructions.

Planning reproduced that result against the untouched local Governance checkout
at `8e4a0a8d943399a90ab92c810b5acdaa4bcd9c04`, despite AGENTS.md declaring
`http://127.0.0.1:8097` and `make dev ACTION=<action>`. Current Governance main
`d1f341dc051cdfd1bb4bbe55764dbb0d8f8ed32d` retains those declarations.
Jig main `50f0d47c275928953dcaa81ee15d68e05cf0a0ae` documents `make dev`
delegating to Baseplate's `scripts/fixture-dev.sh`. Neither declares
`.dm/ui-review.json`. Baseplate main at planning was
`53238bdcce5c85076f68d5f0644cb876bf785fa3`; it owns
`docs/operations/fixture-development.md`, `make smoke-server`, and the generic
Fixture lifecycle. Reacquire consumer heads before proof.

PR #120 delivered proportional case selection, source-capable UI analysis, and
exact packet reuse; its Fixture declaration handoff remains incomplete.
PRs #123, #125, and #126 delivered later routing/portability repairs. Preserve
their behavior. No open Depot Issue or PR existed at prompt preparation.

## Smallest intended change

Apply "Do not guess, but do look" once in the review host before declaring a
target unavailable. Preserve existing explicit-target precedence and accepted
packet reuse. When those do not supply usable evidence, inspect only current
AGENTS.md/CLAUDE.md, their directly named development runbooks, Makefile/Compose
targets, and `tests/ux/verification.json` or named browser handoffs. Retain a
bounded source path/line and exact command/URL reference in existing evidence.

Use only a declaration that clearly identifies the affected application and
selected checkout. Inspect the documented status/readiness command first;
reuse a suitable exact-head target, or execute its documented start/rebuild
procedure within existing resource ownership contracts. Dynamic URLs printed
by that procedure are valid evidence; example ports and production URLs are
not target declarations. Confirm application source/commit and clean/dirty
state before claiming exact-head browser proof. Reachability alone is insufficient.

Keep interpretation in the host. Prefer concise shared instructions and only
the smallest helper input/outcome adjustment needed to preserve repository
source provenance, bounded failure evidence, and existing cleanup. Do not
relabel a discovered repository target as a user-supplied URL. Do not require a
new checked-in declaration merely to use an already documented development loop.
For ambiguous or incomplete declarations, report the exact missing prerequisite
without inventing commands or claiming that no declaration exists.

Likely surfaces, not a mandate to edit all:

- `plugins/dm-review/skills/review/references/ui-review-readiness.md` and `.sh`
- shared review host/dispatch instructions and `skills/visual-test/SKILL.md`
- canonical `plugins/dm-review/commands/` only where entry points duplicate the old rule
- existing `review-docker-create.md`, `review-docker-cleanup.md`, and browser packet contracts
- `tools/test-dm-review-ui-readiness.sh`, `tools/test-dm-review-ui-contract.sh`,
  `tools/test-pipeline-browser-evidence.sh`, and affected workflow validators

## Non-goals

No runbook parser, browser broker, service, new general schema/ledger, port scan,
invented command, model-routing change, broad review redesign, product feature,
consumer release policy, or R-series implementation. Do not edit Baseplate,
Jig, Governance, installed caches, or other active worktrees. Do not auto-reset
or seed persistent developer data. Do not rebuild or stop another session's
target without authority; use a documented isolated target when appropriate.
Do not recreate Fixture-local lifecycle wrappers around Baseplate's launcher.

## Acceptance and focused proof

1. With no invocation URL, T3 attachment, or `.dm/ui-review.json`, an exact
   repository declaration reaches a documented reuse/start/rebuild attempt.
   Cover Governance-style Make delegation and Baseplate-style smoke targets.
2. A real declared command failure produces one `dev_server_unavailable` gap
   with the attempted source/command and bounded failure reason. Reserve
   `visual_target_unavailable` for absence of a repository-owned declaration.
3. Preserve explicit URL and T3 precedence, valid structured declarations,
   dynamic output URLs, and accepted exact-head packet reuse. Reject stale
   source/evidence, ambiguous targets, malformed declarations, and unsafe
   ownership without blind fallback. A target failure and a browser-transport
   failure remain distinct.
4. T3-first browser automation remains host-owned. Test selected affected
   routes/states at desktop and mobile; retain source-only UI/UX analysis and
   one aggregated gap when required rendered evidence cannot run. Never label
   skipped/unavailable coverage clean. Do not expand to a full browser matrix.
5. Reused resources remain untouched. Success, failure, and interruption clean
   only review-created resources through existing recorded ownership.
6. Full, quick, and visual entry points share discovery. Pipeline's final
   review consumes the same contract and still reuses valid exact evidence.

Add meaningful regression cases to existing focused tests, including missing,
documented-but-stopped, failed-command, stale-head, and pre-existing-resource
cases. Keep host instruction scenarios distinct from deterministic helper
tests; source-token assertions alone cannot prove a command was attempted.
Run affected shell syntax checks and the three focused scripts above. Run
`./tools/validate-workflow-contracts.sh`, dual compatibility and dependency
checks, `git diff --check`, and `./tools/validate-composition.sh --all` before
commit. Diagnose failures against the exact base; do not weaken tests or claim
green over unrelated failures. Keep any retained P1/P2/P3 findings fixed before
merge. Use one proportional review and one affected-lane recheck when needed;
do not reopen converged review without new evidence.

Review request: executorRole `review-fast`, executorCapabilities
`[read-repository, long-context, structured-output]`, executorEffort `medium`.
If command execution or cleanup logic changes, additionally request the bounded
`security-review` role with the same capabilities and effort. Resolve both
independently; keep participant identity private.

## Versions, publication, and real consumer canary

Default version movement: dm-review 1.79.1 -> 1.80.0 for the additional
repository-target pattern; reacquire versions and check equal-version remote
collisions first. Update its canonical plugin and marketplace versions.
Regenerate Codex manifests and command aliases with the repository generators;
never hand-edit generated files. Regenerate/check the search index and affected
fixtures. Audit dependency floors. Do not bump Pipeline or other plugins merely
because they consume the shared fix; change a floor and its owning plugin
version only if a new required interface makes that necessary, and explain it.

Before release, prove the branch's exact dm-review source against an isolated,
exact-head Governance or Jig development target using its documented Baseplate
launcher. Read current consumer instructions first and preserve their primary
checkouts. Record all three source heads, selected routes/personas, desktop and
mobile evidence, readiness/start/rebuild commands, duration, and exact cleanup.
Also verify the existing Baseplate smoke declaration discovery without guessing
its port. Synthetic fixtures are local contract proof, not this live canary.
If tooling or a consumer prerequisite prevents completion, retain an honest
coverage gap and a draft PR; finish all independent verification and push.

For Jig, prepare a concise ownership handoff describing the canonical target
declaration/browser handoff it still needs, backed by its existing `make dev`
and Baseplate launcher. Production Fixtures own concrete cases/personas and
target identity. Do not implement that separate consumer change in this branch.

Do not merge, tag, publish, or synchronize installations in this session.
Prepare the exact release checklist: trusted merged-main validation, release
preflight, approved `dm-review-v1.80.0` tag (or actual version), Claude and Codex
cache synchronization, file/version comparison in both caches, then the same
installed-consumer canary. These steps require separate explicit authorization.
Branch-source proof must not be described as released or installed proof.

## Delivery and terminal state

Commit and push the verified implementation. Run release preflight on the clean
commit before push and report all coverage gaps. Open one Depot PR, leave it
unmerged, and keep it draft if required proof remains missing. Do not create,
close, reassign, or substantially rewrite native Issues or unrelated PRs.
Project 1 is the existing Assembly Coordination project: represent only this
active PR as P1 / Tooling; use Review when ready for review, or Blocked with the
named required-evidence dependency. Never mark it Done before its represented
outcome is delivered. Do not create another Project or a free-form backlog card.

Treat approximately 40 tool calls as an exploration checkpoint. Stop new scope
and research there; continue focused repairs, verification, commit, push, PR
handoff, and honest reporting. Do not abandon completed changes uncommitted or
unpushed because of the checkpoint.

Return exact base/head, branch, PR URL/checks, changed Project items, findings
disposition, acceptance evidence, delivery level, and one next action. Include
`SIMPLICITY-CHECK`, `NOT-COVERED`, and `COMMANDS-RUN` with exits. Require one
compact terminal model-and-cost report: role, attempted and served participant,
rail, effort, duration, outcome, measured tokens, measured paid cost,
subscription calls, fallbacks, and unavailable measurements. Keep unknowns
explicit and subscription API-equivalent estimates separate from billed spend.
