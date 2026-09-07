# Depot Efficiency Program -- Phase Index

## Active coordination (2026-09-07, after PR #128 merge)

**Next: finish the existing UI-READY-03 repair and consumer proof.**
[Complete continuation prompt](prompts/ui-ready-03-merged-followup.md).
Do not start another discovery implementation or promote the portfolio chunk.
A follow-up already exists in the original UI-READY worktree. Its session
ownership is pending confirmation; treat it as active and leave it untouched.

### Exact source and delivery evidence

Depot `origin/main` is `bda7cab9ddc97b1bf8746da05ce275584d281031`.
[PR #128](https://github.com/Design-Machines-Studio/depot/pull/128) merged from
`f37d790c4155e8417db043b080e1084dc41da758`; both trees are
`407045a5cb01121635987a00394f91a5f05f03fb`. No open Depot Issue or PR exists.
Hosted Codesmith is SKIPPED, with no submitted GitHub review. The PR records
passing full composition; this coordinator reran the exact committed discovery
suite (54 assertions) and readiness suite (92 assertions), both passing.

Merged code adds bounded host discovery, repository evidence and checkout
binding. It does not prove the successful Docker/Compose-to-browser path:
its helper accepts `pre-existing` or `review-created-process` evidence, while
current Fixture author loops are Docker-only. The local follow-up adds the
Compose ownership handoff. Inspect that candidate separately from merged code;
its working files are not PR #128 evidence.

The PR reports two attempted consumer starts. Governance's documented Baseplate
alpha.16 lacked generated page packages; Baseplate main's smoke container exited
before readiness. These establish attempted startup/failure reporting, not
successful desktop/mobile review. The general-review role was unavailable.
A security review and recheck served, but neither replaces the missing general
review or live canary. Check the documented Baseplate `make templ-generate`
prerequisite before diagnosing a product defect or changing Fixture dependencies.

`dm-review-v1.80.0` does not exist remotely. Codex's installed 1.80.0 matches all
80 tracked files of merged source; Claude remains on 1.79.1. This is partial cache
installation, not a published dual-harness release. Strongest overall delivery:
**merged source with local tests and failed-start evidence; successful consumer
proof, converged general review, publication and both-cache synchronization
remain outstanding**.

OR-EFFORT-01 remains complete at published consumer-proof level: #127 merge
`e3518a1ebef4f299fe9ca009957f15c2f10c1388`, published model-router 0.6.2 and
OpenRouter 1.20.2, both caches and installed Baseplate analysis canary. Its
measured paid call was $0.00521858; no Assembly test execution was claimed.
Do not rerun the completed effort prompts.

| Area | Current version/state | Active problem | Evidence | Consumer impact | Next decision |
|---|---|---|---|---|---|
| Pipeline | 1.66.1 | Successful final-browser path still unproven | Shared dm-review contract | Fixture review cannot yet claim rendered completion | Finish existing UI lane |
| dm-review | 1.80.0 merged; 28-file local follow-up spans related surfaces | Compose handoff and complete consumer proof | Exact helper only accepts process/pre-existing evidence; local repair adds Compose | Documented Docker author loop is the current consumer | Reconcile and finish existing repair |
| model-router | 0.6.2 published/proven | General review unavailable in #128 run | Existing attempt receipts | Missing review is not a clean pass | Retry one bounded role through current routing |
| OpenRouter | 1.20.2 published/proven | Portfolio freshness remains later | Matrix evidence 2026-08-27 | Bounded paid offload is available under budget | No routing change in this chunk |
| Workflow Kernel | 0.19.1 main; 0.20.0 local candidate | Existing local repair adds registry validation for readiness | Uncommitted CLI/runtime/tests in UI worktree | Compose cleanup must retain exact ownership | Retain only demonstrated integration need |
| project-manager | 1.13.0 | Planning needed post-merge correction | Live GitHub/source/cache checks | Prevent duplicate execution | Planning-only maintenance |
| Assembly plugin | 3.16.0 | No plugin blocker selected | Consumer launchers remain repository-owned | Use documented generation and author loop | No Assembly plugin change |
| release/sync | No dm-review 1.80.0 tag; caches differ | Incomplete delivery and active source follow-up | Remote refs and tracked cache byte comparison | Installed behavior differs between harnesses | Repair/prove before release closeout |
| measurement | Existing receipts | R0/R1 aggregate acceptance still incomplete | Single-run tests/cost evidence are not aggregate savings | No supported review-loop saving percentage | Retain original evidence commitments |

### Ownership and consumer boundary

The protected primary remains `bench/gpt-6-astra-screen` at
`6ab616fd5e3bd5c7f2e11ed44677413f0d8de759`, with modified CLAUDE.md and 169
tracked deletions. Ten Depot worktrees are registered: primary, this planning
worktree, UI-READY, completed OR-EFFORT implementation/release, and five historical
pulse/benchmark/review worktrees. This session modifies only its planning branch.

The original UI worktree is
`/home/ned/ai/depot-worktrees/ui-ready-03-repository-target-discovery`, branch
`fix/ui-ready-03-repository-target-discovery`, HEAD `f37d790c4155e8417db043b080e1084dc41da758`.
At inspection it has 28 modified files, including dm-review's helper/contracts,
Workflow Kernel registry/runtime/CLI, validators and generated metadata. No new
PR exposes that work. Do not overwrite, copy or adopt it while its owner is active.
A stopped owner must hand off an exact snapshot before a fresh branch adopts it.

Fresh consumer heads: Baseplate `40dc3cb8d189bc1cdce9a8189822920e4596a03f`,
Governance `4777a292bd4ea52b74bbbc0c82be1524ca0f0299`, Jig
`50f0d47c275928953dcaa81ee15d68e05cf0a0ae`. Governance PR #42 is active at
`16035740e0723e7b5e59d7629aa121557a4524f7`; Baseplate PR #856 and planning
PR #847 are also active. Do not edit their product or instruction surfaces.
Use an isolated compatible declared composition; Governance retains its
`v0.1.1-alpha.16` constraint (`7fa3f108604a2e604e4dc99af5fb96d90b5ae307`).
Jig owns its portable browser declaration and concrete Fixture cases remain
consumer-owned. A consumer startup defect requires a precise owner handoff,
not a Depot product patch or silently changed dependency.

Project 1 item `PVTI_lADODlpzCc4BgGQJzg5uhhk` is Done / P1 / Tooling. Keep it
as the merged PR's source projection; do not claim that it proves UI-READY's full
delivery. Represent a later repair PR separately when it actually exists.
Project changes: **None**. Safe parallel lanes: **None**.

The [model/instruction optimization sequence](model-and-instruction-optimization-20260907.md)
remains intact after this delivery. Historical evidence below remains classified;
no new R-series, model tournament or harness platform scope is authorized.

Planning validation: `./tools/validate-composition.sh --all` passed after this
branch incorporated current main. Planning links, prompt fields, provider-neutral
routing and `git diff --check` passed. No plugin, tool or test differs from main;
this proof does not cover the other worktree's uncommitted candidate.
Release preflight remains blocked by the preserved #128 remote branch carrying
the same untagged 1.80.0 version as merged main. Its plugin tree is identical to
the merged source, and this branch adds only planning documents relative to main.
The user-authorized documentation push does not publish that plugin; no tag,
merge or cache synchronization is performed. Do not report release preflight
as passed or remove another session's branch to silence it.

### Remaining plan disposition

| Plan or commitment | Classification | Evidence / promotion condition |
|---|---|---|
| OR-EFFORT-01 | COMPLETED / PUBLISHED CONSUMER PROOF | #127 merged, both tags/caches verified, installed Baseplate analysis canary; no test-execution claim |
| UI-READY-03 | MERGED SOURCE / ACTIVE FOLLOW-UP / CONSUMER PROOF INCOMPLETE | #128 merged; original worktree has uncommitted Compose/Kernel repair; no tag, general review and successful browser canary outstanding |
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

Historical inventory from the initial audit: ignored plans and receipts in the primary checkout were read without modifying
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
