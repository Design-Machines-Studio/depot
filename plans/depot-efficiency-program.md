# Depot Efficiency Program -- Phase Index

## Active coordination (refreshed 2026-09-07)

**Next: OR-EFFORT-01 -- close out existing PR #127.**
[Complete release-closeout prompt](prompts/or-effort-01-release-closeout.md).
The implementation is open at `0332eac31fb35e3d91b6ddffb056604f49716fd2`,
branch `fix/openrouter-effort-contract`, in its clean existing worktree. Do not
rerun the [original implementation prompt](prompts/or-effort-01-truthful-effort.md).
The coordinator inspected the exact diff and reran the real loopback effort
regression (four levels, read and bounded-write paths) and terminal report
suite (37 assertions): both passed. Full composition is reported in the PR;
hosted Codesmith is SKIPPED and there are no submitted reviews.

PR #126 merged at current main `76267e0e10845e1f9ea4a5eb533b6ca9628b12be`;
it delivered benchmark identity/review compatibility, not OR-EFFORT-01.
PR #127 contains model-router 0.6.2 and OpenRouter 1.20.2. Neither new tag
exists and both harness caches still select 0.6.1/1.20.1. Merge, trusted-main
proof, publication, cache synchronization and the real installed canary remain
pending. Project 1 already has #127 at Review/P1/Tooling; no field change needed.

This follow-up found eight registered Depot worktrees after external cleanup.
The primary still has modified CLAUDE.md and 169 deleted tracked todos; its old
nested benchmark checkout is no longer present. This planning session performed
no cleanup. The inventories below retain the earlier audit snapshot.

The user's system-wide model/instruction audit found that the router reports
normalized effort which the released OpenRouter transport does not send.
[Audit, proposed model defaults, budget and bounded sequence](model-and-instruction-optimization-20260907.md).
UI-READY-03 remains reproduced, prepared and unclaimed; its
[complete prompt](prompts/ui-ready-03-repository-target-discovery.md) follows the
effort repair's delivery. Neither chunk is implemented by this planning branch.

Repository: `Design-Machines-Studio/depot`. Refreshed `origin/main`:
`76267e0e10845e1f9ea4a5eb533b6ca9628b12be`. Authenticated GitHub reports no
open Depot Issues and one open PR (#127). The existing [Assembly Coordination Project
1](https://github.com/orgs/Design-Machines-Studio/projects/1) has 265 items;
#127 is Review/P1/Tooling. No Project fields or native items were
changed by this refresh. Import only active work that advances Assembly.

The primary checkout remains `bench/gpt-6-astra-screen` at
`6ab616fd5e3bd5c7f2e11ed44677413f0d8de759`: modified CLAUDE.md, 169 deleted
tracked todos, and one untracked nested benchmark checkout. All were preserved.
The 24 other pre-existing registered worktrees were clean; recent relevant
heads match merged PRs #116, #118, #120, #121, #123, and #125. Historical
benchmark/pulse worktrees do not establish current implementation ownership.
This coordination refresh uses its own `docs/depot-planning-20260907` worktree.
Do not edit or remove another session's files or worktrees.

### Current source and delivery evidence

| Area | Current version/state | Active problem / consumer impact | Evidence and next decision |
|---|---|---|---|
| Pipeline | 1.66.1 | Final review inherits the target-discovery gap | #116 repository-native proof, #118 prototype authority, #120 packet reuse, #123 routing provenance, #125 scope portability merged; reuse shared dm-review contract |
| dm-review | 1.79.1 | Documented Fixture targets can be reported absent before any start attempt | Reproduced exit 76 against Governance; UI-READY-03 follows the effort repair |
| model-router | 0.6.1 | Computed effort is recorded but omitted from OpenRouter invocation | OR-EFFORT-01 is next; retain #123/#126 discovery, provenance and ordinary-review behavior |
| OpenRouter | 1.20.1 | Wrapper wire request contains no reasoning effort setting | Repair with model-router; portfolio/matrix refresh is separate; installed matrix dated 2026-08-27 |
| Workflow Kernel | 0.19.1 | No newly reproduced scope blocker | #121 observation index and #125 device portability merged; no new state layer needed |
| project-manager | 1.13.0 | This planning index lagged live state | #123 coordinator recommendation behavior is installed; planning-only repair here |
| Assembly plugin | 3.16.0 | Consumer launchers/runbooks remain consumer-owned | Prototype authority and reusable development/release skills are installed; no plugin change selected |
| release/sync | Seven listed versions tagged | Publication alone does not prove a consumer browser journey | Remote tag refs verified; every tracked plugin file matches both local harness caches |
| measurement | Terminal reporting and benchmark bridge implemented | OpenRouter effort is not transmitted; R1 comparable review-loop proof remains unavailable | Repair effort truth first; collect comparable evidence after discovery repair |

The current Pipeline, dm-review, model-router, OpenRouter, and Workflow Kernel
annotated tags peel to PR #126 head
`6ab616fd5e3bd5c7f2e11ed44677413f0d8de759`; that head merged as current main.
project-manager 1.13.0 peels to #123 head `e7bac3439ae643facb27fe2ba3f70b3b5e3d7923`;
Assembly 3.16.0 peels to `0c86ca4d163f5089f6378807be676146dd84c677`.
Claude and Codex cache copies of all seven plugin trees match current main.
No release, tag, or installation was changed in this planning session.

Do not describe hosted CI as green: #120, #123, #125, and #126 expose only
Codesmith SKIPPED, with no formal submitted reviews. Their PR bodies retain
local verification evidence. Current main has zero check runs and no commit
statuses; classic branch protection is absent and the branch-rules endpoint
returns an empty array. No required hosted validation check is configured.
PR #126 reports repaired benchmark fixtures and a passing full Kernel gate;
this refresh separately runs the repository composition validator on clean main.

Planning validation: `./tools/validate-composition.sh --all` passed on the
current-main plugin source with only this planning diff. UI readiness passed
68 assertions, UI contract 30, and Pipeline browser evidence 12. Generated
surfaces, dependencies, Kernel behavior, routing, and index checks passed.
This is fresh local proof against trusted-main source, not hosted CI or a
completed consumer browser journey.

### Retained browser chunk and its ownership boundary

Current `ui-review-readiness.md` stops after an invocation URL, attached T3
preview, or optional `.dm/ui-review.json`; accepted exact Pipeline packets can
replace capture. The helper does not inspect normal repository declarations.
The installed 1.79.1 helper returned `visual_target_unavailable`, exit 76, against
local Governance `8e4a0a8d943399a90ab92c810b5acdaa4bcd9c04`, whose AGENTS.md
names `http://127.0.0.1:8097` and `make dev ACTION=<action>`. No state or resource
was created. This is direct prerequisite-failure proof, not a completed browser
canary or an assertion that the recorded server is running.

Current remote consumers confirm that this is not merely an old checkout:

- Governance `d1f341dc051cdfd1bb4bbe55764dbb0d8f8ed32d` retains the URL and
  Make development actions in AGENTS.md, plus declared desktop/mobile viewports.
- Jig `50f0d47c275928953dcaa81ee15d68e05cf0a0ae` has Make development actions
  delegating to Baseplate and a browser handoff. Both Fixture repositories lack
  `.dm/ui-review.json` and have no open PRs at this refresh.
- Baseplate `53238bdcce5c85076f68d5f0644cb876bf785fa3` owns its documented
  smoke target and [generic Fixture development guide](https://github.com/Design-Machines-Studio/assembly-baseplate/blob/53238bdcce5c85076f68d5f0644cb876bf785fa3/docs/operations/fixture-development.md).

Depot owns bounded host discovery, prerequisite classification, exact-head
proof, and reuse of existing resource cleanup. Jig owns the canonical Fixture
authoring declaration/handoff; production Fixtures own concrete targets,
personas, and cases; Baseplate owns its launcher and lifecycle. UI-READY-03
must not add a general runbook parser, schema, broker, service, or copied
consumer policy. Its live canary uses an isolated exact-head Fixture composition
and desktop/mobile evidence. Prepare the missing Jig handoff; do not implement
consumer changes in the Depot branch. Safe new parallel lanes: **None**.

The former external handoff snapshot is retired: Baseplate #659 and Jig #8 are
closed; Baseplate #681 closed unmerged; #682 merged as
`e1f60f32712816abee2df3572c4b8f2cc56abe3b`. Current consumer roadmaps and
active PRs remain in their owning repositories and Project 1.

### Remaining plan disposition

| Plan or commitment | Classification | Evidence / promotion condition |
|---|---|---|
| UI-READY-03 | ACTIVE / PREPARED | One bounded dm-review branch; no Issue/PR yet; fresh reproduction above |
| R0 measurement backbone | SOURCE COMPLETE; aggregate acceptance UNCERTAIN | Receipts and later instrumentation exist; the original three comparable real-run acceptance tally is not established by this refresh |
| R1 review burn cuts | SOURCE COMPLETE; measurement BLOCKED ON COMPARABLE EVIDENCE | Existing [unusable-baseline notice](../docs/cost-baselines/2026-08-08-r1-review-burn-cuts.unusable.md) requires a real full/selective loop pair; do not substitute implementation bytes or the context-diet percentage |
| R2 pre-gates/evidence reuse | COMPLETED / NO CODE | Existing verification ordering and bounded exact reuse cover the residual; old mechanical-glob policy is not authorized |
| R3 broker/Darwin/FIDO program | SUPERSEDED / REMOVED | #46 and #47 made configured-key execution non-interactive and removed Workflow Authority; no sunset or broker installation remains due |
| R4 old report proposal | SUPERSEDED; evidenced residual COMPLETE | #58 retained rejected attempt evidence; #92 added terminal model/cost reports; do not resurrect a separate report framework |
| R5 interoperability | BOUNDED SOURCE COMPLETE; live-client proof BLOCKED / unavailable | #65 shipped one craft-developer discovery canary; no fleet rollout without an actual client |
| Harness Lessons 01/02 context work | COMPLETED | #78 and #80 landed; recorded four-path context reduction 36.1%, not R1 review-loop proof |
| Old harness-lessons lane claims | PARKED / EVIDENCE-GATED | No current recurring writer collision survives existing worktree isolation |
| Old harness-lessons run budgets / authorization | SUPERSEDED | Existing soft checkpoints and #46/#47 cover the need |
| Old harness-lessons memory capture / codify auto-apply | CAPTURE COMPLETE / AUTO-APPLY REJECTED | #63 landed caller capture; recommendations stay proposal-only; personal systems are optional |
| Factory-throughput, routing-simplicity, phase-triage and depot-main-planner local kits | SUPERSEDED AS EXECUTION SEQUENCES | Ignore old concrete model portfolios, broker dependencies, permissive P3 rules, and stale READY labels |
| Adaptive fusion, initial Kernel, Airlift, chain verification, Assembly release, prototype authority | COMPLETED SOURCE / historical plans | Current plugin capabilities and merged work supersede their prepared prompts; do not rerun the original kits |
| Broad mechanical hardening, old Baseplate-hardening, audience/scaffolder kits, benchmark leftovers | UNCERTAIN RESIDUALS / NOT AUTHORIZED | Partial capability overlap and old local plans are leads only; a current consumer failure must justify a new bounded residual |

Ignored plans and receipts in the primary checkout were read without modifying
or force-adding them. Other registered Depot worktrees reported no untracked
planning files or dirty changes. The old primary `plans/depot-main-planner.md`
and `plans/factory-throughput/prompts/README.md` remain historical, untracked
inputs; this tracked index supersedes their queue and model advice.

### Operating constraints

Use the user priority order: remove current development blockers, then reduce
time/tokens/cost, improve truthful routing and ergonomics, and complete remaining
R-series evidence before unrelated enhancements. The target remains two
maintainers and small self-hosted co-ops of 4-50 users. Every abstraction must
name its current consumer, prevented failure, and replaced complexity.

Request only role, capabilities, and normalized effort from model-router.
Resolve a fresh human recommendation at dispatch; concrete identities stay out
of participant prompts. The existing Astra planning session is available;
nested CLI uncertainty does not disprove parent-session subscription access.
All retained P1/P2/P3 findings must be fixed before merge. Do not manufacture
findings, reopen converged review, or require a full Pipeline for a narrow fix.
Personal memory/Notion systems are silently optional. They were unused in the
initial Depot pulse; the subsequent system audit used personal memory only
after the user's explicit request and did not use Notion.

A source merge, release tag, cache copy, and real consumer run are separate
claims. Record local proof, exact-head CI (or its absence), trusted-main proof,
publication, both caches, and actual consumer proof separately. No new tags,
merges, or synchronization are authorized by this planning refresh.

## Historical program (2026-08-07; not executable)

The following original phase program is retained only as provenance. Its
PENDING/Next labels, fixed models, broker installation steps, and sunset date
do not override the current disposition above. Never dispatch it as written.

Approved plan: `~/.claude/plans/mission-you-are-curious-neumann.md` (2026-08-07).
This file is the run-time index for orchestrators. Each phase directory carries
its own `manifest.json` + `prompts/`. Phases execute through `/pipeline-run`
(or resume, for R3.0) -- never by manual replication (failure mode 1).

Status 2026-08-07 (late): **R0 MERGED** (PR #17; landed stronger than planned --
transactional `emit-cost-summary` + mandatory `record-attempt`; first real
artifact measured 5/5 lanes, 365,216 tokens, $2.996, 100% OpenRouter with Codex
at cap; leftover: baseline copy to docs/cost-baselines/ folded into R1 chunk 01
step 0). **R3.0 MERGED** (PRs #18/#19: chunk 05 packaging + chunk 06 acceptance
harness, 1000-line env-gated integration suite, REQ-E2E-01..12). **R3 chunk 00
DONE** (PR #22): `OPENROUTER_AVAILABLE` now resolves three outcomes and permits
the sunset-bound interim batch only when the broker is absent. R3.1/R3.2 remain
PENDING strictly for broker-owned transport; gate = broker `status: ready` on
a supported host + an executed acceptance pass (`WORKFLOW_AUTHORITY_E2E=1`).
**Next: R1** (prompts refreshed against merged
state; versions now read-current-then-bump).

| Phase | Dir | Prompts | Entry gate | Exit gate |
|-------|-----|---------|-----------|-----------|
| R0 measurement backbone | `plans/r0-measurement-backbone/` | 3 (DONE) | none | >=3 real runs with per-lane cost tables; baselines committed to `docs/cost-baselines/` (1/3 runs done; baseline commit owed -> R1-01 step 0) |
| R1 review burn cuts | `plans/r1-review-burn-cuts/` | 6 | R0 merged (MET) | >=30% drop in review input-bytes on a real loop run, final full fan-out intact |
| P1 probe | scratchpad script, not a phase | 0 | R0 merged | survivor rate recorded; >=40% AND >=2 hunk-local lanes -> R2 reuse chunks live, else killed |
| R2 pre-gates (+ probe-gated reuse) | `plans/r2-pre-gates-evidence-reuse/` | 2 (+2 authored only if probe passes) | R0+R1 merged, probe verdict recorded | real-run bytes delta vs R0 baseline |
| R3 broker landing + routing | `plans/r3-broker-golive-routing/` | 3 (chunk 00 interim macOS operator-batch authorization DONE via PR #22; R3.0 Linux landing DONE via PRs #18/#19; chunks 01/02 parked) | chunk 01: broker `status: ready` on ANY supported host + executed E2E pass | interim: automated OpenRouter lanes on macOS under receipted batch authorization, sunset-bound. final: bulk lanes via broker, interim retired |
| R4 run report (+ gated kernel dispatch) | `plans/r4-run-report/` | 1 now (3 kernel prompts authored only if entry gate met) | report: none. kernel: >=5 runs show orchestration >=20% of residual spend | teammate diagnoses a failed run from the report alone |
| R5 Agent Plugins interop | `plans/r5-agent-plugins-interop/` | 1 | R1 merged | `--check` green in `--all` + preflight; one plugin passes vendored AP schemas |
| Rail-exhaustion ask-gate | `plans/rail-exhaustion-ask-gate/` | 1 | none (answers the 2026-08-08 zero-chunk BLOCKED incident; run at next Codex window, BEFORE the R1 rerun) | rail exhaustion pauses on human_gate with live per-operator rail status and receipted run-scoped authorization; headless default park; broker gate + final review + sensitive paths never overridable |

R3.0 resume steps (no new prompts -- finish the paid-for run):
1. In the Codex clone, merge `pipeline/macos-authority-broker/05-linux-packaging-admin`
   into `ai/workflow-authority-linux-m1` and record its completion receipt.
2. Execute the existing `plans/macos-authority-broker/prompts/06-linux-integration-acceptance.md`
   through the same run (`workflow-authority-linux-m1-20260803`), its gates unchanged.
3. Reconcile the feature branch with current main (main's kernel 0.8.0 content wins on overlap).
4. Full dm-review-loop (security class = full tier, zero-deferral), merge to main.
5. Clean the eight `04b-*`/`04c-*`/`04d-*`/`04e-*`/`04f-*` sub-worktrees + branches per
   the repo-cleanup contract with a Branch & Worktree Inventory.

Darwin broker milestone: AUTHORED at `plans/darwin-broker-milestone/`
(2 chunks, security class): 01 darwin platform layer + launchd packaging +
peer credentials; 02 darwin ops/validator/acceptance + AKIA-vector defang.
Retires interim mode on macOS once Travis performs the live install/enroll
per OPERATIONS.md darwin section. Run AFTER the chain-verification queue
completes (no file conflicts with it, but serialize merges). Sunset
2026-09-07; Linux hosts return ~2026-08-22.

Harness-lessons phase was historically AUTHORED at `plans/harness-lessons/`
(4 chunks). The 2026-08-15 reassessment makes that local plan provenance only:
lane claims are parked, run budgets are solved/obsolete, authorization friction
is solved/superseded, and PR #63 completed the caller-side memory-capture
residual. Codify auto-apply is rejected; recommendations remain proposal-only.

Kill switches introduced by this program (all fail OPEN to full coverage; every
receipt records active switches): `DM_REVIEW_LOOP_FULL_FANOUT`,
`DM_REVIEW_FULL_DIFF`, `PIPELINE_FULL_TIER_REVIEW`, `PIPELINE_NO_GATE_ONLY`,
`DM_REVIEW_NO_EVIDENCE_REUSE` (probe-gated chunk only).
